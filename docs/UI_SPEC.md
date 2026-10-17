# Vadesiz – UI and workflow spec (v2)

Copilot: implement this spec on top of the existing code. Keep `fraud.py`, `gemma.py`, `mocks.py`
logic; change `app.py` and `db.py`, add files only where listed.

## 1. Look and feel: white, corporate, public-sector style
- Light theme only. Create `.streamlit/config.toml`:
  ```toml
  [theme]
  base = "light"
  primaryColor = "#0B3D91"
  backgroundColor = "#FFFFFF"
  secondaryBackgroundColor = "#F4F6FA"
  textColor = "#1F2937"
  font = "sans serif"
  ```
- Inject one CSS block from `ui.py` (new file) on every page:
  - Top bar: full-width navy (`#0B3D91`) strip, white text "VADESİZ · Fatura Finansman Platformu",
    right side: logged-in company name + role badge + "Çıkış".
  - Thin red accent line (`#C8102E`, 3px) under the top bar.
  - Content max-width 1100px, centered, generous white space, cards with 1px `#E5E7EB` border,
    8px radius, subtle shadow, 24px padding.
  - Buttons: navy filled primary, white with navy border secondary, 6px radius.
  - Tables: zebra rows, header `#F4F6FA`, no Streamlit default dataframe look where possible.
  - Hide Streamlit menu, footer and "Deploy" button.
  - Footer: small grey text "Demo amaçlıdır · GİB, Findex, banka ve e-imza entegrasyonları mock'tur".
- Do NOT use any real government logo, name or emblem. Public-sector *style* only.

## 2. Login: separate entry per role
- Landing page = login screen: centered card, Vadesiz wordmark, three tabs:
  **KOBİ Girişi**, **Finansör Girişi**, **Denetim Girişi** (fraud detector / admin).
- Demo accounts seeded in SQLite (password hashed with `hashlib.pbkdf2_hmac`, never plain text):
  - KOBİ: one account per SME in `data/companies.json` (type `sme`), username = VKN, password `demo1234`.
  - Finansör: `anadolu_faktoring`, `firat_finans`, `harput_katilim` – password `demo1234`.
  - Denetim: `denetim` – password `demo1234`.
  - Show these demo credentials in a collapsed "Demo hesapları" expander under the login card.
- After login, only that role's pages are visible. "Çıkış" clears the session.
- Every login attempt is written to the audit log (success or fail).

## 3. SQL database (`vadesiz.db`, schema in `db.py`)
```
users(id, username UNIQUE, password_hash, salt, role CHECK(role IN ('kobi','finansor','denetim')),
      company_vkn, display_name, email)
uploads(id, uploaded_at, user_id, company_vkn, ip_address, user_agent, file_name, file_size,
        file_sha256, invoice_no, invoice_fingerprint, extracted_json, risk_score, flags_json,
        status CHECK(status IN ('incelemede','teklif_bekliyor','teklif_var','finanse_edildi','reddedildi')))
offers(id, upload_id, financier_user_id, created_at, discount_rate, net_amount, note,
       status CHECK(status IN ('beklemede','kabul','red','geri_cekildi')))
notifications(id, user_id, created_at, channel CHECK(channel IN ('panel','email')), subject, body, read_at)
audit_log(id, at, user_id, username, ip_address, action, detail_json)
```
- IP address: `st.context.ip_address` (fallback "127.0.0.1"). User agent: `st.context.headers.get("User-Agent")`.
- `file_sha256` = SHA-256 of the uploaded file bytes. `invoice_fingerprint` = existing fraud fingerprint.
- Upload of a file whose `file_sha256` already exists → reject with HTTP 409 and audit `duplicate_upload`.
  A matching `invoice_fingerprint` is not auto-rejected: keep status `incelemede`, add the
  `duplicate_invoice` flag, and route it to the Denetim review queue.
- Actions to audit: `login`, `login_failed`, `logout`, `upload`, `upload_failed`, `duplicate_upload`, `extract`,
  `offer_created`, `offer_accepted`, `offer_rejected`, `transfer_mock`.
- Denetim role gets a page **"Kayıt Defteri"**: filterable table of `uploads` and `audit_log`
  (company, date range, action) with columns: time, company, user, IP, file, SHA-256 (shortened with
  full value on hover), invoice no, risk, status. CSV export button.

## 4. KOBİ panel
Pages (sidebar or top tabs): **Fatura Yükle**, **Faturalarım**, **Bildirimler**.

### Fatura Yükle (card-based, like a clean application form)
- Centered card, big document icon, title "Faturanızı yükleyin", short help text.
- Step indicator at the top: ① Yükle → ② Okuma → ③ Kontrol → ④ Teklife aç.
- Dashed-border drag & drop area (style Streamlit's `st.file_uploader` with CSS):
  "Faturayı buraya sürükleyin veya seçin · PNG, JPG, PDF · en fazla 10 MB". PDF files are rendered
  locally to a PNG of the first page before Gemma reads them.
- **Remove the demo sample dropdown.** The user uploads real files only.
- After upload: show file name, size, SHA-256 (short), a small preview thumbnail.
- "Faturayı oku" button → Gemma extracts → editable form with the fields (KOBİ can correct) →
  "Kontrol et" → fraud flags with Turkish labels + Gemma explanation, risk shown as a coloured badge
  (0–29 düşük/yeşil, 30–59 orta/turuncu, 60+ yüksek/kırmızı).
- "Finansmana aç" button → status `teklif_bekliyor`. Risk ≥ 60 → status `incelemede` (goes to Denetim first).
- **No automatic offer.** Nothing appears until a financier actually makes an offer.

### Faturalarım
- Table of the company's uploads: invoice no, buyer, total, due date, risk badge, status, offer count.
- Clicking a row opens a detail card. Offers are shown in a **separate card on the right side**
  (two-column layout), each offer as a compact row: financier, net amount, discount rate,
  date, "Kabul et" / "Reddet". Under the list: Gemma `compare_offers` recommendation in a grey info box.
- Accept → mock bank transfer, upload status `finanse_edildi`, other offers `red`, notifications sent.

### Bildirimler
- Inbox of `notifications` for this user, unread ones bold. Badge with unread count in the top bar.
- When a financier makes an offer: insert a `panel` notification **and** an `email` notification
  (mock: also append the email to `logs/outbox.log` with to/subject/body; never send real mail).

## 5. Finansör panel
Pages: **Fatura Pazarı**, **Tekliflerim**.

### Fatura Pazarı (marketplace list first, no offer form until a row is chosen)
- Filter bar: sector, amount range, due within (30/60/90/120 days), max risk.
- Table of uploads with status `teklif_bekliyor` or `teklif_var`: seller (KOBİ) name, buyer name,
  amount, due date, days left, buyer mock credit score, risk badge, number of offers so far.
  Data comes from the uploads table **plus** the existing `data/invoices.json` (shown as already
  uploaded by their sellers, so the market is not empty).
  **Exception:** invoices whose `invoice_no` appears in one of the images in `samples/` are NOT
  preloaded (their invoice numbers are listed in `data/demo_uploads.json`). Those are the files the presenter uploads live,
  so they must not be treated as duplicates. They are still used by the fraud graph/network checks.
- Selecting a row opens a detail drawer/card: invoice fields, flags, Gemma risk report, suggested
  discount from the deterministic formula, and only then the offer form (discount rate → net amount
  auto-calculated, optional note, "Teklif ver").
- One active offer per financier per invoice; can withdraw.

### Tekliflerim
- Table of own offers with status; accepted ones show "Finanse edildi" and the mock transfer receipt.

## 6. Denetim panel
Pages: **Dedektör** (existing graph), **İnceleme Kuyruğu** (uploads with status `incelemede`,
approve → `teklif_bekliyor`, reject → `reddedildi` with a reason), **Kayıt Defteri** (section 3).

## 7. Done when
- Login works for all three roles with the demo accounts.
- A KOBİ can upload a PNG from outside the repo, see SHA-256, read with Gemma, open it to financing.
- A financier sees it in the market, makes an offer; the KOBİ gets a panel + email notification.
- KOBİ accepts; status becomes `finanse_edildi`; everything appears in Kayıt Defteri with IP and hash.
- Uploading the same file again is rejected as duplicate.
