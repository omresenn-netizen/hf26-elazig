# Payment-delay forecast

VadeX builds one chronological feature row per payment in `payment_history`. Inputs are
amount, due month, buyer sector, employee count, buyer age at the due date, the average
delay of the previous three settled payments, and days since the latest settled payment.
Rolling features use only payments settled before the target due date, so the target
payment's outcome and unsettled-payment outcomes are not included.
The targets are `days_late` for regression and `days_late > 5` for classification.

The service uses the CPU TabPFN v2 pretrained checkpoints (four estimators) and caches
both fitted estimators in process memory. The model is loaded and fitted on the first
forecast request, then reused. No fallback model or synthetic response is used if the
checkpoint cannot be downloaded or loaded.

## Evaluation

`python forecast.py` evaluates the latest 20% of distinct due dates as a chronological
holdout. MAE is reported in days; accuracy uses a 0.5 threshold for the `>5 days late`
classification target. Re-run the command after changing payment history or the TabPFN
version so the recorded metrics match the data and checkpoints being used.

| Metric | Result |
| --- | --- |
| Holdout split | Due dates before 2026-07-03 / 2026-07-03 onward |
| Training / test rows | 160 / 41 |
| MAE | 4.36 days |
| Accuracy | 78.05% |

Measured with `tabpfn` 9.2.0, CPU, and the TabPFN v2 checkpoints against the repository's
201 fictional payment rows. The test portion is the latest 20% by distinct due date.

This dataset is a small fictional demonstration, not a credit decision dataset.
Forecasts are advisory and must not replace human review.
