import math
from datetime import date

import pytest

import forecast


def _companies():
    return {
        "buyer-1": {
            "vkn": "buyer-1",
            "sector": "retail",
            "employees": 80,
            "founded": 2000,
        }
    }


def _payments():
    return [
        {
            "id": index,
            "company_vkn": "buyer-1",
            "counterparty_vkn": f"seller-{index}",
            "amount": 1000 + index * 100,
            "due_date": f"2025-{index:02d}-15",
            "paid_date": f"2025-{index:02d}-15",
            "days_late": 8 if index % 2 else 0,
        }
        for index in range(1, 13)
    ]


def test_training_features_use_only_previous_payments():
    rows = forecast.build_training_table(_payments(), _companies())

    first = rows[0]["features"]
    fourth = next(row for row in rows if row["due_date"] == date(2025, 4, 15))["features"]
    assert first["buyer_sector"] == "retail"
    assert first["buyer_employees"] == 80
    assert first["buyer_age"] == 25
    assert first["previous_3_avg_days_late"] == 0
    assert fourth["previous_3_avg_days_late"] == pytest.approx((8 + 0 + 8) / 3)
    assert fourth["days_since_previous_payment"] == 31
    assert rows[0]["late"] == 1


def test_unpaid_prior_due_date_does_not_leak_its_delay():
    payments = _payments()
    payments[2]["paid_date"] = "2025-05-20"

    april = next(
        row for row in forecast.build_training_table(payments, _companies())
        if row["due_date"] == date(2025, 4, 15)
    )["features"]

    assert april["previous_3_avg_days_late"] == 4
    assert april["days_since_previous_payment"] == 59


def test_time_holdout_splits_by_due_date():
    rows = forecast.build_training_table(_payments(), _companies())
    due_dates = sorted({row["due_date"] for row in rows})
    split_index = max(1, min(len(due_dates) - 1, int(len(due_dates) * 0.8)))
    split_date = due_dates[split_index]
    assert all(row["due_date"] < split_date for row in rows if row["due_date"] < split_date)
    assert any(row["due_date"] >= split_date for row in rows)


def test_time_holdout_reports_metrics(monkeypatch):
    monkeypatch.setattr(
        forecast,
        "_fit_models",
        lambda training: (_MetricRegressor(), _MetricClassifier()),
    )

    result = forecast.evaluate_time_holdout(_payments(), _companies())

    assert result["train_rows"] == 9
    assert result["test_rows"] == 3
    assert result["split_date"] == "2025-10-15"
    assert result["mae"] == 0
    assert result["accuracy"] == 1


def test_tabpfn_forecast_on_synthetic_table(monkeypatch):
    pytest.importorskip("tabpfn", reason="TabPFN is not installed; install requirements.txt to run model tests.")
    monkeypatch.setattr(forecast, "_MODELS", None)
    monkeypatch.setattr(forecast, "_load_history", _payments)
    monkeypatch.setattr(forecast, "_load_companies", _companies)

    result = forecast.forecast_delay("buyer-1", 2500, "2026-02-15")

    assert result["model"] == "TabPFN"
    assert result["n_train"] == 12
    assert math.isfinite(result["expected_days_late"])
    assert 0 <= result["late_probability"] <= 1
    assert result["features"]["previous_3_avg_days_late"] == pytest.approx((0 + 8 + 0) / 3)


class _MetricRegressor:
    def predict(self, features):
        return [8 if int(month) % 2 else 0 for month in features["month"]]


class _MetricClassifier:
    classes_ = [0, 1]

    def predict_proba(self, features):
        return [[0.25, 0.75] if int(month) % 2 else [0.75, 0.25] for month in features["month"]]
