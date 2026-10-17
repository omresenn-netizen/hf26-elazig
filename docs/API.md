# VadeX HTTP API (contract between `web/` and `server.py`)

FastAPI app in `server.py`, run with `uvicorn server:app --port 8600`.
Serves the static front end from `web/` at `/` and the JSON API under `/api`.
Session: Starlette `SessionMiddleware` cookie (secret from env `VADEX_SECRET`, random if missing).
Client IP: `request.client.host`; user agent: `request.headers["user-agent"]`.
Reuse `db.py`, `fraud.py`, `gemma.py`, `mocks.py` (and `repo_*.py` if present). Do not duplicate their logic.
Errors: JSON `{"error": "<Turkish message>"}` with a proper status code (400/401/403/404/409).
All money values are numbers in TL. Dates are ISO `YYYY-MM-DD`.

## Common objects
```
User      {id, username, role: "kobi"|"finansor"|"denetim", display_name, company_vkn}
Flag      {code, label (Turkish), detail}
Document  {id ("U-12" for uploads, "INV-001" for preloaded invoices.json), invoice_no, type: "Fatura",
           seller {vkn, name, sector}, buyer {vkn, name, credit_score}, total, subtotal, kdv,
           issue_date, due_date, days_left, irsaliye_no, status, risk_score (0-100),
           risk_class ("A" <30, "B" 30-59, "C" 60-79, "D" 80+), flags [Flag], offer_count, best_offer,
           file {name, size, sha256, uploaded_at, ip_address} | null,
           steps [{key, label, state: "done"|"running"|"failed"|"waiting", detail}]}
Offer     {id, document_id, financier {id, name}, net_amount, discount_rate, annual_rate, note,
           created_at, status: "beklemede"|"kabul"|"red"|"geri_cekildi"}
```
`steps` keys, in order: `upload` (Belge yüklendi), `extract` (Gemma ile okuma), `gib` (GİB e-Fatura sorgusu – MOCK),
`fraud` (Naylon fatura kontrolü), `buyer` (Alıcı onayı ve risk – MOCK).
Status values: `incelemede`, `teklif_bekliyor`, `teklif_var`, `finanse_edildi`, `reddedildi`.

## Auth
- `POST /api/login` `{role, username, password}` → `{user}`; audit `login` / `login_failed`.
- `POST /api/logout` → `{ok: true}`; `GET /api/me` → `{user}` or 401.
- `GET /api/demo-accounts` → list of demo usernames per role (no passwords) for the login hint.

## KOBİ
- `POST /api/uploads` multipart `file` (PNG/JPG/PDF, ≤ 10 MB, checked by magic bytes) → `{document}`
  with status `incelemede` and steps `upload` done. A previously uploaded file SHA-256 → 409.
  A matching invoice fingerprint is flagged `duplicate_invoice` and stays in `incelemede` for Denetim review.
  `data/demo_uploads.json` invoices must not count as duplicates on their first upload.
- `POST /api/documents/{id}/extract` → runs `gemma.extract_invoice` → `{fields}` (editable by the user).
  PDF files are rendered locally to a PNG of their first page before Gemma reads them.
- `POST /api/documents/{id}/check` `{fields}` → GİB mock + fraud rules + `gemma.explain_flags`
  → `{document, explanation}`.
- `POST /api/documents/{id}/publish` → risk < 60: `teklif_bekliyor`; risk ≥ 60: stays `incelemede` (review queue).
- `GET /api/my/documents` → `[Document]` of the logged-in KOBİ.
- `GET /api/documents/{id}` → `{document, offers: [Offer]}` (KOBİ: own only; financier: market docs only).
- `GET /api/documents/{id}/compare` → `gemma.compare_offers` → `{recommendation, reason}`.
- `POST /api/offers/{id}/accept` → mock bank transfer, document `finanse_edildi`, other offers `red`,
  notifications to all financiers involved → `{document, receipt}`.
- `POST /api/offers/{id}/reject` → `{offer}`.
- `GET /api/stats` → `{financed_total, waiting_count, offer_count, avg_discount}` for the KOBİ.

## Finansör
- `GET /api/market?q=&min=&max_days=&risk=&sector=&sort=amount|due` → `[Document]` with status
  `teklif_bekliyor`/`teklif_var`, uploads + preloaded invoices (except `data/demo_uploads.json` numbers).
- `GET /api/documents/{id}/risk-report` → `gemma.risk_report` (cached per id) + deterministic
  suggested discount → `{summary, suggested_discount_rate, suggested_net_amount}`.
- `GET /api/documents/{id}/delay-forecast` (finansör, denetim, owning KOBİ) → TabPFN prediction for
  the invoice buyer: `{expected_days_late, late_probability, model, n_train, features}`. The
  forecast is also supplied to Gemma's risk-report context.
- `POST /api/offers` `{document_id, net_amount, note}` → one active offer per financier per document,
  updating replaces it. Creates `panel` + `email` notifications for the KOBİ (email appended to
  `logs/outbox.log`, never sent). → `{offer}`.
- `DELETE /api/offers/{id}` → withdraw. `GET /api/my/offers` → `[Offer + document summary]`.
- `GET /api/portfolio` → won documents, invested, expected collection, expected profit.

## Denetim
- `GET /api/review-queue` → `[Document]` with status `incelemede` and risk ≥ 60.
- `POST /api/documents/{id}/review` `{decision: "approve"|"reject", reason}`.
- `GET /api/audit?company=&action=&from=&to=` → audit rows `{at, username, company, ip_address, action,
  file_name, sha256, invoice_no, detail}`; `GET /api/audit.csv` same as CSV.
- `GET /api/network` → `{nodes: [{id, name, sector, total, flagged}], edges: [{source, target, total,
  invoice_count, flagged}]}` from `data/invoices.json` + uploads.
- `POST /api/network/report` → Gemma Turkish report for the flagged cluster → `{report}`.

## Notifications (all roles)
- `GET /api/notifications` → `[{id, created_at, subject, body, read}]`; `POST /api/notifications/read`.

## v2 additions – AI visibility (owner: ai-insights agent)
Every AI response carries `"model": "gemma4"` and `"generated_at"`. Cache per object id in memory or DB.
- `GET /api/documents/{id}/insight` (KOBİ owner, financier, denetim) → Gemma commentary on the invoice:
  `{summary, strengths: [str], concerns: [str], verdict: "uygun"|"dikkat"|"riskli", model, generated_at}`.
- `GET /api/companies/{vkn}/payment-profile` (financier, denetim; KOBİ only for its own buyers) →
  `{company {vkn, name, sector, founded, employees}, stats {invoice_count, on_time_ratio (0-1),
  avg_days_late, max_days_late, volume_12m}, history: [{invoice_no, due_date, paid_date, amount, days_late}]
  (last 12 rows, newest first), ai_comment: str, model, generated_at}`. Data from the `payment_history` table.
- `GET /api/documents/{id}/offers-insight` (KOBİ owner) → Gemma comments on every active offer:
  `{offers: [{offer_id, financier, net_amount, discount_rate, annual_rate, comment}], recommendation, reason,
  model, generated_at}`.
- `GET /api/my/ai-digest` (any role) → 3–5 short Turkish bullet points about the user's current situation
  (KOBİ: waiting offers/expiring due dates; financier: best opportunities by risk/return; denetim: suspicious
  clusters) → `{bullets: [str], model, generated_at}`.
- Fixes: `annual_rate = discount_rate / max(days_left,1) * 365`; `GET /api/notifications` returns only
  `panel` notifications (email copies stay in `logs/outbox.log`); offers and documents read from the DB on every
  request so a financier's offer is visible to the KOBİ immediately.

## v2 additions – data (owner: db-architect agent)
- Table `payment_history(id, company_vkn, invoice_no, counterparty_vkn, amount, due_date, paid_date, days_late)`,
  seeded once from `data/payment_history.json` (generated by `scripts/make_payment_history.py`): 12–24 rows per
  buyer company, realistic: big buyers mostly on time (0–5 days late), one buyer with a worsening trend.
- `db.get_payment_history(vkn, limit=24)` and `db.payment_stats(vkn)` helpers.
- Indexes on uploads(file_sha256), uploads(invoice_fingerprint), offers(upload_id), audit_log(at), notifications(user_id).
- SQLite triggers making `audit_log` append-only (UPDATE/DELETE raise an error).
- `PRAGMA foreign_keys=ON`, WAL mode.

## Role checks
Every endpoint checks the session role. Every state change writes `db.log_audit` with IP and user agent.
