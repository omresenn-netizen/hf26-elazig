# Project: TBD (Hacktoberfest 2026, Elazığ fest)

> The project idea is not decided yet. This file will be updated once it is.

## Context
Built from scratch tonight for Hacktoberfest 2026 ("Side Hustle" theme): a small, specific tool
built with open-weight models / open-source AI that a real person would pay for.

## Fixed decisions
- Python 3.13
- Gemma 4 via local Ollama: HTTP API at `http://localhost:11434`, model name `gemma4`
  (supports text, vision, audio, tools). Use `/api/chat`; send `"think": false` unless reasoning is needed.
- No OpenAI / Anthropic / other cloud AI SDKs: the core must run on open models.

## Rules
- Keep code simple and readable; this is a one-night project. Prefer few files.
- Code, comments and README in English.
- Every call to Gemma must be logged: append one JSON line per call to `logs/gemma.jsonl`
  with timestamp, prompt, raw response and duration in seconds. Use a single helper function for all Gemma calls.

## Git
- After every task that leaves the project in a working state, commit it yourself:
  `git add -A` then `git commit -m "<short English message>"`. One commit per finished step.
- Do not push; the user pushes from VS Code.
- Never commit secrets, `.env`, or large model files.
