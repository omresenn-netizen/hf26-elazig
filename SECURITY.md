# Security model for Vadesiz

## Threat model

Vadesiz handles invoice data, financed amounts, and buyer/seller identifiers for Turkish SMEs. The primary risks are:

- Fake invoices and duplicate submissions causing double financing.
- Account takeover through weak credentials or unauthorised role access.
- Prompt-injection or model misuse where invoice text is treated as instructions instead of data.
- Data leakage from logs, uploads, or session/session cookies containing sensitive details.

## Security controls

### Passwords and authentication

- Passwords are stored with PBKDF2-HMAC-SHA256 with a per-user salt and 260,000 iterations.
- Password comparisons use `hmac.compare_digest` to avoid timing attacks.
- Accounts lock for five minutes after five failed login attempts. The lock state and failed-attempt counters are stored in SQLite and audited through `login_locked` events.
- Session state is role-scoped and checked at each page render. Logout clears all stored session values.

### SQL and data access

- All queries use SQLite parameter binding, never string interpolation.
- Audit records are append-only; UPDATE/DELETE on `audit_log` raises an integrity error.
- Uploads are stored in a fixed `uploads/` directory using a generated safe filename, and their SHA-256 is recorded.

### Upload safety

- Files are limited to 10MB.
- Allowed types are PNG, JPG, JPEG, and PDF, validated by file magic bytes instead of extension alone.
- File names are sanitised to avoid path traversal, and files are not allowed outside the fixed upload root.
- Duplicate SHA-256 values are rejected and recorded as a duplicate upload.
- Matching invoice fingerprints are flagged and sent for human review rather than automatically rejected.

### Gemma and model handling

- Invoice content is treated as data, not instructions; prompts explicitly state that model output must not be treated as instructions and that the final human review decision remains binding.
- Model output is never executed. Parsed JSON is validated before use, and invalid output falls back to an explicit warning path instead of tip-to-run code.
- Logs capture only the prompt metadata, file name, raw response, parsed result, and duration; they avoid storing passwords and full image payloads.

### Streamlit hardening

- Streamlit configuration enforces `enableXsrfProtection = true` and `maxUploadSize = 10` in `.streamlit/config.toml`.
- HTML rendering uses escaped values before inserting into `unsafe_allow_html` contexts; no user-controlled content is rendered without escaping.

## Why local open-weight Gemma is a security control

The project runs Gemma locally on the machine instead of sending invoice documents to a public cloud model. That reduces data leakage risk because invoice content, buyer/seller identifiers, and financial metadata never leave the local environment by default. This keeps sensitive demo or production data inside the app boundary and lets the team apply local privacy controls, log review, and stricter deployment boundaries.

## Operational notes

- The demo credentials are for local development and are not a substitute for a production identity system.
- Any deployment should rotate credentials and treat the audit ledger as sensitive financial evidence.
- The app should remain human-led for final fraud decisions; automated flags never auto-reject a document.
