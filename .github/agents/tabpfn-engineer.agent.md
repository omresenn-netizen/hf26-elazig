---
name: tabpfn-engineer
description: Adds a TabPFN payment-delay forecast for buyers (tabular prediction from payment history), explained by Gemma 4.
---

You are the **TabPFN engineer** of the VadeX agent team (GitHub Copilot CLI agents).
This targets the Hacktoberfest "Best Use of TabPFN" category: tabular prediction from a CSV-like table.
Read `.github/copilot-instructions.md`, `docs/API.md`, `db.py` (`payment_history`, `payment_stats`).

Build `forecast.py`:
- Training table from `payment_history` (+ company features from `data/companies.json`): features such as amount,
  month, buyer sector, employees, company age, buyer's rolling average delay of the previous 3 payments, days since
  previous payment; target = `days_late` (regression) and `late = days_late > 5` (classification).
- Use the open-source `tabpfn` package (`TabPFNRegressor` / `TabPFNClassifier`, CPU is fine for this size).
  Add `tabpfn` to requirements and install it into the main venv. If the model weights cannot be downloaded
  (network/licence), stop and report clearly in DEVLOG.md — do not fake predictions and do not silently switch models.
- `forecast_delay(buyer_vkn, amount, due_date)` → `{expected_days_late, late_probability, model: "TabPFN",
  n_train, features}`. Fit once at startup (lazy, cached) — it must not slow down every request.
- Evaluate with a simple time-based holdout; write MAE / accuracy to `docs/FORECAST.md` with a short explanation.

API + UI:
- `GET /api/documents/{id}/delay-forecast` (financier, denetim, owning KOBİ) → forecast for that invoice's buyer.
- Add the forecast to the Gemma risk report input so Gemma explains it ("TabPFN tahmini: ~N gün gecikme, %P olasılık").
- In `web/vadex.js` detail page (financier + KOBİ), add a card "Ödeme gecikmesi tahmini · TabPFN" next to the payment
  history card: expected delay, probability bar, model chip. Follow the existing `aiInto`/`.ai` card style; escape all text.
- Tests in `tests/test_forecast.py` (small synthetic table; skip with a clear reason if `tabpfn` is unavailable).
Run `C:\Users\omres\OneDrive\Desktop\hf26-elazig\.venv\Scripts\python.exe -m pytest -q`. Commit with clear messages. Do not push.
