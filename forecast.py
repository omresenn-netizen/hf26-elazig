"""TabPFN payment-delay forecasts from the audited payment history."""
import json
import math
import threading
from datetime import date
from pathlib import Path

import db

ROOT = Path(__file__).resolve().parent
COMPANIES_PATH = ROOT / "data" / "companies.json"
FEATURE_NAMES = (
    "amount",
    "month",
    "buyer_sector",
    "buyer_employees",
    "buyer_age",
    "previous_3_avg_days_late",
    "days_since_previous_payment",
)
_MODELS = None
_MODELS_LOCK = threading.Lock()


def _load_history():
    with db.get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, company_vkn, counterparty_vkn, amount, due_date, paid_date, days_late
            FROM payment_history
            ORDER BY company_vkn, due_date, id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def _load_companies():
    with COMPANIES_PATH.open(encoding="utf-8") as source:
        companies = json.load(source)
    if not isinstance(companies, list):
        raise ValueError("data/companies.json must contain a JSON array.")
    return {str(company["vkn"]): company for company in companies}


def _company_features(buyer_vkn, due_date, companies):
    company = companies.get(str(buyer_vkn), {})
    founded = company.get("founded")
    return {
        "buyer_sector": str(company.get("sector") or "bilinmiyor"),
        "buyer_employees": float(company.get("employees") or 0),
        "buyer_age": max(due_date.year - int(founded), 0) if founded else 0,
    }


def _feature_row(buyer_vkn, amount, due_date, previous, companies):
    previous_delays = [int(row["days_late"]) for row in previous[-3:]]
    previous_paid = date.fromisoformat(previous[-1]["paid_date"]) if previous else None
    return {
        "amount": float(amount),
        "month": due_date.month,
        **_company_features(buyer_vkn, due_date, companies),
        "previous_3_avg_days_late": (
            sum(previous_delays) / len(previous_delays) if previous_delays else 0.0
        ),
        "days_since_previous_payment": (
            (due_date - previous_paid).days if previous_paid else 0
        ),
    }


def build_training_table(records, companies):
    """Build chronological features without using the current or future payment."""
    grouped = {}
    for row in records:
        buyer_vkn = str(row["company_vkn"])
        date.fromisoformat(str(row["due_date"])[:10])
        date.fromisoformat(str(row["paid_date"])[:10])
        grouped.setdefault(buyer_vkn, []).append(row)

    rows = []
    for buyer_vkn, payments in grouped.items():
        payments.sort(
            key=lambda row: (
                str(row["due_date"])[:10],
                str(row.get("id", row.get("invoice_no", ""))),
            )
        )
        for payment in payments:
            due_date = date.fromisoformat(str(payment["due_date"])[:10])
            previous = [
                row for row in payments
                if row is not payment and str(row["paid_date"])[:10] < due_date.isoformat()
            ]
            previous.sort(
                key=lambda row: (
                    str(row["paid_date"])[:10],
                    str(row.get("id", row.get("invoice_no", ""))),
                )
            )
            rows.append(
                {
                    "features": _feature_row(
                        buyer_vkn,
                        payment["amount"],
                        due_date,
                        previous,
                        companies,
                    ),
                    "target": int(payment["days_late"]),
                    "late": int(int(payment["days_late"]) > 5),
                    "due_date": due_date,
                }
            )

    rows.sort(key=lambda row: row["due_date"])
    return rows


def _feature_frame(rows):
    import pandas as pd

    return pd.DataFrame(rows, columns=FEATURE_NAMES)


def _fit_models(rows):
    try:
        from tabpfn import TabPFNClassifier, TabPFNRegressor
        from tabpfn.constants import ModelVersion
    except ImportError as exc:
        raise RuntimeError(
            "TabPFN is not installed. Install the declared tabpfn dependency."
        ) from exc

    if len(rows) < 2:
        raise ValueError("At least two historical payments are required for TabPFN.")
    if len({row["late"] for row in rows}) < 2:
        raise ValueError("TabPFN classification requires both late and on-time examples.")

    features = _feature_frame([row["features"] for row in rows])
    targets = [row["target"] for row in rows]
    labels = [row["late"] for row in rows]
    try:
        regressor = TabPFNRegressor.create_default_for_version(
            ModelVersion.V2,
            device="cpu",
            n_estimators=4,
            categorical_features_indices=[2],
            random_state=42,
        )
        classifier = TabPFNClassifier.create_default_for_version(
            ModelVersion.V2,
            device="cpu",
            n_estimators=4,
            categorical_features_indices=[2],
            random_state=42,
        )
        regressor.fit(features, targets)
        classifier.fit(features, labels)
    except Exception as exc:
        raise RuntimeError(
            "TabPFN v2 could not load its pretrained weights or fit the payment history; "
            "check network access and the Prior Labs model license."
        ) from exc
    return regressor, classifier


def _models():
    global _MODELS
    if _MODELS is None:
        with _MODELS_LOCK:
            if _MODELS is None:
                rows = build_training_table(_load_history(), _load_companies())
                _MODELS = (*_fit_models(rows), len(rows))
    return _MODELS


def forecast_delay(buyer_vkn, amount, due_date):
    """Predict late days and the chance of a payment being over five days late."""
    due_date = date.fromisoformat(str(due_date)[:10])
    amount = float(amount)
    if not math.isfinite(amount) or amount < 0:
        raise ValueError("amount must be a finite, non-negative number.")

    history_cutoff = min(due_date, date.today())
    history = [
        row for row in _load_history()
        if str(row["company_vkn"]) == str(buyer_vkn)
        and str(row["paid_date"])[:10] < history_cutoff.isoformat()
    ]
    history.sort(key=lambda row: (str(row["paid_date"]), row["id"]))
    features = _feature_row(
        str(buyer_vkn),
        amount,
        due_date,
        history,
        _load_companies(),
    )
    regressor, classifier, n_train = _models()
    prediction = float(regressor.predict(_feature_frame([features]))[0])
    classes = list(classifier.classes_)
    late_class_index = classes.index(1)
    probability = float(classifier.predict_proba(_feature_frame([features]))[0][late_class_index])
    if not math.isfinite(prediction) or not math.isfinite(probability):
        raise RuntimeError("TabPFN returned a non-finite payment-delay forecast.")
    probability = min(max(probability, 0.0), 1.0)
    return {
        "expected_days_late": round(prediction, 2),
        "late_probability": round(probability, 4),
        "model": "TabPFN",
        "n_train": n_train,
        "features": features,
    }


def evaluate_time_holdout(records=None, companies=None, holdout_fraction=0.2):
    """Measure TabPFN on the latest due-date portion of the payment history."""
    if not 0 < holdout_fraction < 1:
        raise ValueError("holdout_fraction must be between zero and one.")
    records = _load_history() if records is None else records
    companies = _load_companies() if companies is None else companies
    rows = build_training_table(records, companies)
    dates = sorted({row["due_date"] for row in rows})
    if len(dates) < 2:
        raise ValueError("At least two distinct due dates are required for a time holdout.")
    cutoff = max(1, min(len(dates) - 1, int(len(dates) * (1 - holdout_fraction))))
    split_date = dates[cutoff]
    training = [row for row in rows if row["due_date"] < split_date]
    testing = [row for row in rows if row["due_date"] >= split_date]
    regressor, classifier = _fit_models(training)
    test_features = _feature_frame([row["features"] for row in testing])
    predictions = regressor.predict(test_features)
    probabilities = classifier.predict_proba(test_features)
    classes = list(classifier.classes_)
    late_class_index = classes.index(1)
    actual_targets = [row["target"] for row in testing]
    actual_labels = [row["late"] for row in testing]
    late_predictions = [
        row[late_class_index] >= 0.5 for row in probabilities
    ]
    return {
        "train_rows": len(training),
        "test_rows": len(testing),
        "split_date": split_date.isoformat(),
        "mae": sum(
            abs(float(prediction) - actual)
            for prediction, actual in zip(predictions, actual_targets)
        ) / len(testing),
        "accuracy": sum(
            int(bool(prediction) == bool(actual))
            for prediction, actual in zip(late_predictions, actual_labels)
        ) / len(testing),
    }


if __name__ == "__main__":
    db.init_db()
    print(json.dumps(evaluate_time_holdout(), indent=2))
