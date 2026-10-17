# Vadesiz

**Invoice financing for Turkish SMEs, with a local open-weight model that catches fake invoices.**

Hacktoberfest 2026 – Elazığ fest project.

## The problem
Small businesses sell to big companies and get paid 60–120 days later. To survive the gap they
turn to loan sharks or, worse, to the fake-invoice ("naylon fatura") market.

## What Vadesiz does
1. A small business uploads a real invoice.
2. **Gemma 4** (running locally via Ollama) reads it and runs fake-invoice checks:
   delivery note, sector/item match, capacity, round amounts, buyer approval, duplicate use,
   and circular invoice rings in the seller→buyer network.
3. Licensed financiers see verified invoices with a Gemma risk report and bid to buy them.
4. The business gets cash today; the big buyer pays the financier on the due date.

## Why an open model?
Banks and factoring companies cannot send customers' financial data to a cloud AI API.
Gemma runs on the platform's own machine, so the data never leaves it, and reading thousands of
invoices costs nothing per call.

## Demo data
All companies, tax numbers and invoices in `data/` and `samples/` are fictional.
GİB e-Fatura verification, credit scores and bank transfers are mocked.
Regenerate with `python scripts/make_demo_data.py`.

## Built with
Gemma 4 · Ollama · GitHub Copilot (agent mode, coding agent, PR review) · Python · Streamlit · networkx

## Check the setup
```
powershell -ExecutionPolicy Bypass -File scripts\check_setup.ps1
```

## License
MIT
