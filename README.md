# Vadesiz

**Local-first invoice financing demo for Turkish SMEs.**

Hacktoberfest 2026 — Elazığ fest project.

Small businesses often wait 60–120 days to be paid. Vadesiz demonstrates how a business
could upload an invoice, review local AI extraction and deterministic risk flags, then
compare financing offers without sending invoice data to a cloud AI API.

## Current demo

- **Login and audit:** role-specific KOBİ, financier and auditor login tabs with seeded
  demo accounts. Passwords are stored as salted PBKDF2-HMAC hashes. Login attempts,
  logout and invoice file processing are written to SQLite with request IP metadata;
  uploads also retain the browser user-agent and file SHA-256. Auditors can search and
  export the activity ledger.

- **KOBİ paneli:** select a fictional sample invoice or upload a PNG/JPG; Gemma extracts
  fields, rule checks show Turkish-labelled flags and a risk score, and the user can
  review offers and accept one using a simulated transfer.
- **Finansör paneli:** browse demo invoices, inspect their risk score and status, view a
  Gemma risk report and mock buyer credit score, then save a net-amount/discount offer.
  The base discount is calculated deterministically from the 45% annual rate, time to
  maturity and risk premium (with a 0.5% minimum); Gemma explains the result, and the
  report is cached per invoice/input context.
- **Dedektör:** explore the interactive seller-to-buyer invoice graph, review the top
  ten risk-scored invoices, and request a Turkish Gemma summary of red-flagged networks.
- **Shared metrics:** invoice count, GİB verification count, invoices under review and
  accepted financing volume appear across all three panels.

Risk flags support human review and never automatically reject an invoice. Invoice data,
companies, tax numbers and sample images are fictional. GİB verification, buyer credit
scores and bank transfers are deterministic **DEMO / MOCK** responses.

Every demo account uses password `demo1234`. SME usernames are the VKNs listed in
`data/companies.json`; financier usernames are `anadolu_faktoring`, `firat_finans` and
`harput_katilim`; the auditor username is `denetim`. Runtime tables are created
idempotently in the ignored `vadesiz.db`; existing demo offers and deals are preserved
during the schema upgrade.

## Run locally

Requirements: Python 3.13 and Ollama with the `gemma4` model available locally.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
ollama pull gemma4
streamlit run app.py
```

The app is available at `http://localhost:8501`. Gemma runs through the local Ollama
HTTP API; each call is appended to `logs/gemma.jsonl`. Runtime offers and deals are stored
in the ignored local `vadesiz.db`.

## Stack

Python · Streamlit · Ollama/Gemma 4 · SQLite · networkx · PyVis

## Development setup check

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_setup.ps1
```

## License

MIT
