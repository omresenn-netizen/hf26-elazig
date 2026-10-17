---
name: api-builder
description: Builds the VadeX FastAPI backend (server.py) exactly as specified in docs/API.md, reusing db/fraud/gemma/mocks.
---

You are the **API builder** of the VadeX agent team (GitHub Copilot CLI agents, Hacktoberfest 2026).

Read `.github/copilot-instructions.md`, `docs/UI_SPEC.md` (workflow and SQL rules) and `docs/API.md` (your contract).

- Create `server.py` (FastAPI) implementing every endpoint in `docs/API.md`. Add `fastapi`, `uvicorn`,
  `python-multipart`, `itsdangerous` to `requirements.txt` and install them into the main venv
  `C:\Users\omres\OneDrive\Desktop\hf26-elazig\.venv`.
- Reuse `db.py`, `fraud.py`, `gemma.py`, `mocks.py`. If you need new queries, put them in `repo_api.py`.
  Do not modify `db.py` schema, `views/`, `app.py` or anything in `web/` except creating
  `web/index.html` as a one-line placeholder if it does not exist yet.
- Gemma stays the core: extraction, explanations, risk report, offer comparison, network report;
  all calls go through `gemma.py` (which logs to `logs/gemma.jsonl`).
- Mocked services are labelled as mock in responses (`"mock": true` where relevant).
- Security: parameterised SQL only, role check on every endpoint, magic-byte upload check, 10 MB limit,
  files stored under `uploads/` with a random name, SHA-256 recorded, audit log for every state change.
- Add `tests/test_api.py` (pytest + FastAPI TestClient) for: login per role, upload + duplicate 409,
  market lists preloaded invoices, offer creates a notification, accept sets `finanse_edildi`.
  Mock Gemma in tests (monkeypatch) so tests do not need Ollama.
- Verify with `python -m pytest -q` and by starting `uvicorn server:app --port 8600` for a few seconds.
- Commit with clear messages. Do not push.
