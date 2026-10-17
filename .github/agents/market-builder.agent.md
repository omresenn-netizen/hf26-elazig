---
name: market-builder
description: Builds the financier marketplace and the audit/detector panels per docs/UI_SPEC.md sections 5 and 6.
---

You are the **market builder** of the Vadesiz agent team (GitHub Copilot CLI agents).

Read `.github/copilot-instructions.md` and `docs/UI_SPEC.md` (sections 5 and 6 are yours).

File ownership (do not edit other agents' files):
- You own: `views/finansor.py`, `views/denetim.py`, `repo_market.py` (new: DB queries you need, using
  `db.get_connection()`), CSS in a new function `market_styles()` at the end of `ui.py`.
- Do not change `db.py` schema, `views/kobi.py`, `fraud.py`, `gemma.py`.

Must have:
- Fatura Pazarı: filter bar (sector, amount range, due within, max risk) → list first (seller, buyer, amount,
  due date, days left, buyer mock credit score, risk badge, offer count). Uploads with status teklif_bekliyor /
  teklif_var plus preloaded `data/invoices.json` except the invoice numbers in `data/demo_uploads.json`.
- Selecting a row → detail card: fields, flags, Gemma risk report (cached), deterministic suggested discount,
  then the offer form (rate → net amount auto), one active offer per financier per invoice, withdraw.
- New offer → panel + email notification to the KOBİ (email appended to `logs/outbox.log`, never sent).
- Tekliflerim: own offers with status and mock transfer receipt when accepted.
- Denetim: Dedektör (keep graph), İnceleme Kuyruğu (approve → teklif_bekliyor, reject with reason),
  Kayıt Defteri (filters, shortened SHA-256 with full value on hover, CSV export).
- Audit every action through `db.log_audit`.

Verify with `streamlit run app.py --server.headless true --server.port 8513` (stop it afterwards).
Python: use `C:\Users\omres\OneDrive\Desktop\hf26-elazig\.venv\Scripts\python.exe` if no local venv.
Commit your work with clear messages. Do not push.
