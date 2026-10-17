"""Generate deterministic fictional payment history for buyer and SME companies."""
import json
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SEED = 26
HISTORY_DAYS = 548
WORSENING_BUYER = "Doğu Yapı Market A.Ş."
REFERENCE_DATE = date(2026, 10, 18)


def payment_delay(company, days_ago, rng):
    if company["name"] == WORSENING_BUYER and days_ago <= 120:
        if days_ago <= 59:
            return rng.randint(34, 40)
        if days_ago <= 79:
            return rng.randint(27, 33)
        if days_ago <= 99:
            return rng.randint(21, 26)
        return rng.randint(15, 20)
    if company["type"] == "buyer":
        return 0 if rng.random() < 0.65 else rng.randint(1, 5)
    return rng.randint(-2, 12)


def build_payment_history(companies, today=None):
    today = today or REFERENCE_DATE
    rng = random.Random(SEED)
    eligible = [company for company in companies if company["type"] in {"buyer", "sme"}]
    buyers = [company for company in eligible if company["type"] == "buyer"]
    smes = [company for company in eligible if company["type"] == "sme"]
    records = []

    for company in eligible:
        row_count = rng.randint(12, 24)
        if company["name"] == WORSENING_BUYER:
            recent_offsets = [
                40 + month * 20 + rng.randint(0, 19)
                for month in range(4)
            ]
            offsets = recent_offsets + [
                rng.randint(121, HISTORY_DAYS)
                for _ in range(row_count - len(recent_offsets))
            ]
        else:
            offsets = [rng.randint(1, HISTORY_DAYS) for _ in range(row_count)]

        counterparties = smes if company["type"] == "buyer" else buyers
        for index, days_ago in enumerate(sorted(offsets), start=1):
            due_date = today - timedelta(days=days_ago)
            days_late = payment_delay(company, days_ago, rng)
            days_late = min(days_late, days_ago)
            paid_date = due_date + timedelta(days=days_late)
            counterparty = rng.choice(counterparties)
            records.append({
                "company_vkn": company["vkn"],
                "invoice_no": f"PH-{company['vkn'][-4:]}-{index:04d}",
                "counterparty_vkn": counterparty["vkn"],
                "amount": round(
                    rng.uniform(50_000, 1_500_000)
                    if company["type"] == "buyer"
                    else rng.uniform(10_000, 250_000),
                    2,
                ),
                "due_date": due_date.isoformat(),
                "paid_date": paid_date.isoformat(),
                "days_late": days_late,
            })
    return records


def main():
    companies = json.loads((DATA / "companies.json").read_text(encoding="utf-8"))
    records = build_payment_history(companies)
    (DATA / "payment_history.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Generated {len(records)} payment history records for buyer and SME companies.")


if __name__ == "__main__":
    main()
