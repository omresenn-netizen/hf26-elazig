# Task: cancel wrong uploads, detect non-invoice images, clean draft rows

Reported by the user in the browser (KOBİ `9200000101`, Hazar Tekstil):
1. A wrong image (a food photo) was uploaded. Gemma returned empty fields and there is no way to remove the upload.
2. "Belgelerim" shows empty rows (no invoice no / buyer) and a garbage row with invoice no `2211`: uploads that were
   never read or were read badly.

Implement (API in `server.py`/`repo_api.py`/`db.py`, UI in `web/vadex.js`, docs in `docs/API.md`):

A. **Cancel an upload** – `DELETE /api/documents/{id}` for the owning KOBİ, allowed only while the upload has no offers
   and is not financed. Do not physically delete DB rows (audit log is append-only): set status `reddedildi`,
   store reason "Kullanıcı tarafından iptal edildi", delete the stored file from `uploads/`, write audit `upload_cancelled`.
   A user-cancelled upload must not block re-uploading the same file or invoice (exclude it from the SHA-256 and
   fingerprint duplicate checks). Financiers and the market never see cancelled uploads.

B. **Not an invoice** – after `extract`, if Gemma's result has no invoice number AND no total AND neither seller nor
   buyer VKN/name, return `{"fields": ..., "not_invoice": true, "message": "Bu görsel bir fatura gibi görünmüyor."}`.
   Also add an instruction to the `extract_invoice` prompt: if the image is not an invoice, return all fields null.
   UI: show the message with two buttons: "Yüklemeyi sil" (calls DELETE, returns to step 1) and "Elle doldur".

C. **Wizard** – on steps 2 and 3 add a secondary "Vazgeç ve yüklemeyi sil" button (confirm dialog) that calls DELETE.

D. **Belgelerim** – uploads without a valid invoice number (missing, shorter than 6 characters, or never checked) are
   shown as drafts: file name in the "Belge no" column, badge "Taslak", buyer "–", and a "Devam et" (opens the wizard for
   that document) and "Sil" action. Cancelled uploads are hidden unless the status filter is "Reddedildi".
   The KPI and digest must ignore drafts and cancelled uploads.

E. Tests: cancel → status reddedildi + audit + file gone + same file can be uploaded again; not_invoice detection;
   financier cannot see cancelled; cannot cancel when an offer exists.

Run `C:\Users\omres\OneDrive\Desktop\hf26-elazig\.venv\Scripts\python.exe -m pytest -q`, `node --check web/vadex.js`,
bump the `?v=` asset version in `web/index.html`. Commit with clear messages. Do not push.
