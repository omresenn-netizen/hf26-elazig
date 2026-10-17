---
name: writer
description: Writes the English DEV challenge post draft and the Turkish 3-minute pitch/demo script from the real project history.
---

You are the **writer** of the VadeX agent team (GitHub Copilot CLI agents).
Writing quality is the heaviest judging criterion. Be concrete, honest and specific; no marketing fluff.

Read: `README.md`, `DEVLOG.md`, `SECURITY.md`, `docs/API.md`, `docs/DEPLOY.md`, `.github/agents/*.agent.md`,
`sessions/*.md` (agent session exports), `logs/gemma.jsonl` (count calls per task, typical durations), `git log`.

1. `docs/DEV_POST.md` – English DEV post for the Hacktoberfest 2026 Open-Source AI Challenge, Week 2 "Side Hustle".
   Front matter tags: `devchallenge, hf26challenge, opensource, ai`. Structure:
   - Hook: a real phone call — someone asked a family member to issue a 200k TL invoice for a commission
     ("naylon fatura"). Explain the fake-invoice economy and the cash crunch behind it in 2 short paragraphs.
   - What VadeX is and who pays (factoring companies/banks per deal, SaaS for big buyers).
   - Why open weights win here (financial data cannot leave the bank; cost per invoice; no lock-in) — the judges' question.
   - How Gemma 4 is used (each task, with real numbers from `logs/gemma.jsonl`), including the VKN OCR slip it made
     and how the system reconciles it — human stays in the loop.
   - How it was built: GitHub Copilot in VS Code agent mode, then a team of Copilot CLI custom agents in parallel git
     worktrees (list them and what each did, with commit counts). Embed/link the session files.
   - Demo walkthrough with the seeded data; screenshots placeholders `![...](TODO)`.
   - Limitations and mocks (GİB, Findex, bank, e-signature are simulated), what's next.
   - Team section with placeholders for DEV usernames, prize categories entered (Gemma, GitHub Copilot, TabPFN if
     `forecast.py` exists, Entire), repo link https://github.com/omresenn-netizen/hf26-elazig, MIT license.
   - AI disclosure paragraph: code written mainly by GitHub Copilot agents; Gemma 4 inside the product; Claude was
     used as an assistant for planning, review and parts of the front end.
2. `docs/PITCH.md` – Turkish 3-minute pitch + live demo script for the jury: who speaks when, which screen, which
   demo account (`9200000505`, `anadolu_faktoring`, `denetim`, broker `9300000904`), which sample file to upload
   (`samples/04_naylon_danismanlik.png` → risk 90 → review queue; `samples/01_gercek_icecek.png` → clean), the
   expected Gemma waits and what to say meanwhile, and 5 likely jury questions with short answers.
Commit with clear messages. Do not push.
