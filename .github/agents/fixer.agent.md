---
name: fixer
description: Fixes the findings of the code review and removes dead code and tracked build artefacts, without changing features.
---

You are the **fixer** of the VadeX agent team (GitHub Copilot CLI agents).
Read `.github/copilot-instructions.md`, `docs/API.md`, `docs/UI_SPEC.md`, `SECURITY.md`.

Fix these review findings (verify each one in the code first; if a finding is wrong, leave a note in DEVLOG.md instead):
1. **Duplicates:** an upload whose file SHA-256 already exists stays rejected with HTTP 409 (exact same file).
   An upload whose *invoice fingerprint* matches an earlier one (different file, same invoice) must NOT be auto-rejected:
   set status `incelemede`, add the `duplicate_invoice` flag, and let the Denetim review queue decide. Same in the
   Streamlit tool (`views/kobi.py`, `db.py`).
2. **Upload rollback vs append-only audit:** when saving the file fails, do not delete audit rows. Write a
   `upload_failed` audit entry, mark the upload row `reddedildi` with reason, and return a clean 500 JSON error.
3. **Financing volume:** `db.financing_volume()` and every KPI must include deals created by the new API flow
   (`deals.offer_id` NULL / `offers` table), not only `legacy_offers`.
4. **PDF uploads:** Gemma reads images only. Convert the first page of a PDF to PNG before `gemma.extract_invoice`
   (use `pypdfium2`, add to requirements), or reject PDFs at upload with a clear Turkish message — prefer converting.
5. Dead code: remove `_RISK_REPORT_CACHE` if unused (update tests), remove unused legacy helpers in `db.py` and
   `mocks.e_signature` only after `grep` proves no caller (Streamlit views included).
6. Repository hygiene: stop tracking `vadesiz.db.bak-*` and `logs/outbox.log` (add to `.gitignore`, `git rm --cached`).
   Keep `logs/gemma.jsonl` and `logs/agent-*.log` tracked on purpose: they are the evidence of Gemma and Copilot use.

Add or update pytest tests for 1–4. Run `C:\Users\omres\OneDrive\Desktop\hf26-elazig\.venv\Scripts\python.exe -m pytest -q`.
Commit with clear messages. Do not push.
