# Security model for VadeX

## Threat model

VadeX handles invoice data, financed amounts, and buyer/seller identifiers for Turkish SMEs. The primary risks are:

- Fake invoices and duplicate submissions causing double financing.
- Account takeover through weak credentials or unauthorised role access.
- Prompt-injection or model misuse where invoice text is treated as instructions instead of data.
- Data leakage from logs, uploads, or session cookies containing sensitive details.

The controls below map to the actual implementation and tests in the repository.

| Threat | Control | Where in code | Proof in tests | Commit / evidence |
| --- | --- | --- | --- | --- |
| Fake invoice or duplicate financing | SHA-256 fingerprint and review queue; duplicate uploads are marked and kept in review | [fraud.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/fraud.py), [repo_api.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/repo_api.py), [db.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/db.py) | [tests/test_security.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/tests/test_security.py) | [857d7eb](https://github.com/omresenn-netizen/hf26-elazig/commit/857d7eb) |
| Account takeover | PBKDF2 + salt + lockout after repeated failures | [db.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/db.py), [repo_api.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/repo_api.py) | [tests/test_security.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/tests/test_security.py) | [02c0a2c](https://github.com/omresenn-netizen/hf26-elazig/commit/02c0a2c) |
| Role-based access bypass | `session_user()` and `require_role()` guard document and action endpoints | [server.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/server.py) | [tests/test_api.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/tests/test_api.py) | [6d9c33c](https://github.com/omresenn-netizen/hf26-elazig/commit/6d9c33c) |
| Upload validation bypass | size limits and magic-byte checks for PNG/JPG/PDF | [views/kobi.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/views/kobi.py), [server.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/server.py) | [tests/test_security.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/tests/test_security.py) | [02c0a2c](https://github.com/omresenn-netizen/hf26-elazig/commit/02c0a2c) |
| Prompt injection or untrusted document text | Document text is treated as data, not instructions; output is parsed and validated | [gemma.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/gemma.py), [server.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/server.py) | [tests/test_gemma.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/tests/test_gemma.py) | [b03c18e](https://github.com/omresenn-netizen/hf26-elazig/commit/b03c18e) |
| Audit tampering | Append-only `audit_log` triggers reject UPDATE and DELETE | [db.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/db.py) | [tests/test_db.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/tests/test_db.py) | [9378e86](https://github.com/omresenn-netizen/hf26-elazig/commit/9378e86) |
| Data leakage | Local Ollama model, no cloud AI upload, and `scenario` field stripped before API exposure | [repo_api.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/repo_api.py), [gemma.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/gemma.py) | [tests/test_api.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/tests/test_api.py) | [c4325bc](https://github.com/omresenn-netizen/hf26-elazig/commit/c4325bc) |
| XSS / unsafe rendering | Output escaping before HTML rendering | [app.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/app.py), [views](https://github.com/omresenn-netizen/hf26-elazig/tree/main/views) | [tests/test_api.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/tests/test_api.py) | [30cca5e](https://github.com/omresenn-netizen/hf26-elazig/commit/30cca5e) |
| Dependency security scanning | Bandit + pytest in CI; security checks run on PRs and pushes | [.github/workflows/ci.yml](https://github.com/omresenn-netizen/hf26-elazig/blob/main/.github/workflows/ci.yml) | [tests](https://github.com/omresenn-netizen/hf26-elazig/tree/main/tests) | [ecbe8a8](https://github.com/omresenn-netizen/hf26-elazig/commit/ecbe8a8) |

## Security controls

### Passwords and authentication

- Passwords are stored with PBKDF2-HMAC-SHA256 and a per-user salt.
- Password comparisons use `hmac.compare_digest` to avoid timing attacks.
- Accounts lock after repeated login failures, and the lockout is stored in SQLite and audited through the `login_locked` event path.
- Session state is role-scoped and checked at each page render; logout clears stored session values.

See [db.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/db.py) and [repo_api.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/repo_api.py).

### SQL and data access

- All queries use SQLite parameter binding rather than string interpolation.
- Audit records are append-only; UPDATE/DELETE on `audit_log` is blocked by triggers.
- Uploads are stored in a fixed `uploads/` directory with generated safe names and recorded SHA-256 checksums.

See [db.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/db.py) and [repo_api.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/repo_api.py).

### Upload safety

- Files are limited to 10 MB.
- Allowed types are PNG, JPG, JPEG, and PDF, validated by file magic bytes rather than extension alone.
- Duplicate SHA-256 values are rejected and recorded as duplicate uploads.
- Matching invoice fingerprints are flagged for human review instead of auto-rejection.

See [views/kobi.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/views/kobi.py) and [server.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/server.py).

### Gemma and model handling

- Invoice content is treated as data, not instructions; prompts explicitly state that model output must not be used as instructions.
- Model output is never executed. Parsed JSON is validated before use, and invalid output falls back to an explicit warning path instead of running code.
- Logs capture only the prompt metadata, file name, raw response, parsed result, and duration; they do not store passwords or full image payloads.

See [gemma.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/gemma.py).

### Streamlit / UI hardening

- `enableXsrfProtection` and `maxUploadSize` are set in the app configuration.
- Escaping is used before inserting values into HTML contexts; no user-controlled content is rendered unsafely.

See [app.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/app.py) and the files under [views](https://github.com/omresenn-netizen/hf26-elazig/tree/main/views).

## Why local open-weight Gemma is a security control

The project runs Gemma locally on the machine instead of sending invoice documents to a public cloud model. That reduces data leakage risk because invoice content, buyer/seller identifiers, and financial metadata stay inside the local environment by default. It also keeps the model under the lender’s deployment control and is an important trust property for a financial workflow.

See [gemma.py](https://github.com/omresenn-netizen/hf26-elazig/blob/main/gemma.py) and [logs/gemma.jsonl](https://github.com/omresenn-netizen/hf26-elazig/blob/main/logs/gemma.jsonl).

## Operational notes

- The demo credentials are for local development and are not a substitute for a production identity system.
- Any deployment should rotate credentials and treat the audit ledger as sensitive financial evidence.
- The app remains human-led for final fraud decisions; automated flags never auto-reject a document.

## Reporting a vulnerability

If you find a security issue in this repository, please follow the standard private disclosure path: do not open a public issue with exploit details. Instead, report the issue to the maintainer with a concise description, impact, reproduction steps, and any suggested remediation. Avoid sharing credentials, invoice data, or private files. The project treats invoice and account details as sensitive information and expects responsible disclosure.
