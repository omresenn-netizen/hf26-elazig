---
title: "VadeX: local-first invoice fraud checks for batch-funded SMEs"
tags: [devchallenge, hf26challenge, opensource, ai]
---

# VadeX: local-first invoice fraud checks for cash-crunched SMEs

A real phone call was the spark: one family member asked another to issue a 200k TL invoice for a commission, and the question was not about legality — it was about speed. That is the economics behind the fake-invoice market: a seller needs cash now, buyers want a receipt they can pass through a system, and someone in the middle quietly turns paper into liquidity. In Turkey, this is often described as a "naylon fatura" problem, and it flourishes when cash is tight and paperwork is easy to manipulate.

The core problem is not abstract fraud math; it is payment timing. Most SMEs sell goods to bigger companies and wait 60–120 days to get paid. A legal invoice-financing market solves that by letting a business sell the invoice to a financier at a discount and receive cash today, while the buyer eventually pays the financier on the due date. That is the business model VadeX makes legible: the invoice itself becomes a trusted asset, not just a document.

## What VadeX does

VadeX helps an SME upload an invoice, extract the key fields with Gemma 4, and run rule-based anti-fraud checks before any financing offer is accepted. A financier sees a ranked list of documents with risk scores, buyer credit context and a suggested discount range. A reviewer can inspect a suspicious cluster and decide whether to approve it, reject it, or send it back for more evidence. The money moves through a mock transfer flow, but the important part is the decision support layer: risk is shown, explained, and kept human-led.

The buyers of the platform are straightforward: factoring companies and banks pay per deal when they fund a valid invoice, while larger corporate buyers can subscribe to a SaaS layer that gives them cleaner, lower-risk invoice approvals and zero-friction payment visibility. This is a financing workflow that aims to create trust without sacrificing speed.

## Why open weights win here

This is the project question judges usually care about: why not just send every invoice to a cloud model? In invoice finance, the document contains seller and buyer identifiers, financial amounts, contract details and payment timing. That is sensitive data. The rails are not public social content; they are financial records. Keeping the model local matters because the invoice does not have to leave the machine boundary, and the system can keep the risk controls and explainability in-house.

Open weights are also practical in a financial workflow. We can run Gemma 4 locally on a laptop or GPU box, pay per inference rather than per document sent to a third-party API, and avoid vendoring our underwriting logic into one cloud provider. The result is a lower-cost, more portable trust layer that still keeps the final decision with a human. We did not build a black box; we built a local reasoning assistant that can be audited and reviewed.

## How Gemma 4 is used

Gemma 4 is the nervous system of the app, but it stays bounded and transparent. The project logs each call to `logs/gemma.jsonl`, following the exact local-first pattern in the repo. The recorded task mix is concrete evidence of what the model is doing:

- `extract_invoice`: 12 calls, average ~7.06s
- `explain_flags`: 41 calls, average ~3.11s
- `risk_report`: 13 calls, average ~5.07s
- `compare_offers`: 5 calls, average ~2.87s
- plus a handful of network, insight and digest calls for the later AI visibility work

The most important operational detail is that the model is not trusted blindly. When OCR sees a Turkish VKN or company name, the system reconciles it against the registry in `data/companies.json` and against known invoice metadata before surfacing anything as trusted. In other words, we treat the model as a fast extractor and explainer, not as the final source of truth. If the extracted VKN does not line up with the known seller or an invoice ring, we keep it in the human-review path. That is the key safety boundary for any financial AI tool.

Each Gemma task is explicit and limited:

- `extract_invoice`: read the image or PDF page and return structured fields only
- `explain_flags`: take the rule outputs and explain them in Turkish in plain language, without assigning guilt
- `risk_report`: summarize invoice risk and suggest a discount range for the financier
- `compare_offers`: compare financing offers and rank the best option

The app also includes a human-first policy: no invoice is auto-rejected because of a flag. Suspicious documents stay in review, which is exactly what a real lender would do.

## How it was built

The project began with GitHub Copilot in VS Code Agent mode, then grew into a team of dedicated Copilot CLI agents working in parallel git worktrees. Each agent had a narrow ownership boundary, and the sessions were exported into the repo so the project history remains readable and reviewable.

- `agent/architect` — system shape and repo-wide flow, with the main session in [sessions/01-architect.md](../sessions/01-architect.md)
- `agent/kobi-builder` — KOBİ upload, invoice review, offer handling, and notifications in [sessions/02-kobi-builder.md](../sessions/02-kobi-builder.md)
- `agent/market-builder` — financier marketplace, audit flow, and review queue in [sessions/02-market-builder.md](../sessions/02-market-builder.md)
- `agent/api-builder` — FastAPI contract and backend behavior in [sessions/02-api-builder.md](../sessions/02-api-builder.md)
- `agent/db-architect` — payment history + SQLite integrity and analytics in [sessions/02-db-architect.md](../sessions/02-db-architect.md)
- `agent/ai-insights` — cached AI explanations and user digests in [sessions/02-ai-insights.md](../sessions/02-ai-insights.md)
- `agent/devops` — deployment and CI infrastructure in [sessions/02-devops.md](../sessions/02-devops.md)
- `agent/security-auditor` — hardening auth, audit logs, and upload safety in [sessions/02-security-auditor.md](../sessions/02-security-auditor.md)
- `agent/fixer` — invoice-flow, review, and financing corrections in [sessions/02-fixer.md](../sessions/02-fixer.md)
- `agent/tabpfn-engineer` — payment-delay forecast integration in [sessions/02-tabpfn-engineer.md](../sessions/02-tabpfn-engineer.md)
- `agent/integrator` — final merge, validation, and handoff in [sessions/03-integrator.md](../sessions/03-integrator.md) and [sessions/04-integrator.md](../sessions/04-integrator.md)

Commit counts across the worktree branches tell the story of the parallel build:

- kobi-builder: 20 commits
- market-builder: 20 commits
- api-builder: 22 commits
- db-architect: 31 commits
- ai-insights: 31 commits
- devops: 31 commits
- security-auditor: 39 commits
- fixers and forecasting work: 47 commits each

This was not a single giant patch; it was a coordinated team build with ownership boundaries and versioned checkpoints.

## Demo walkthrough

The repository includes seeded fictional data for a realistic walkthrough. A KOBİ user can log in with a company VKN such as `9200000505`, upload a document like `samples/04_naylon_danismanlik.png`, and then see the red flags surfaced: vague description, capacity outlier, and no delivery-note evidence. The system intentionally leaves it in a review queue rather than auto-rejecting it. A cleaner file such as `samples/01_gercek_icecek.png` can be used to show the happy path: clean extraction, validated seller/buyer data and a low-risk offer path.

The UI also supports a financier view and an auditor view, with the network graph used to highlight circular invoicing and shell-company patterns. That is where the anti-fraud story becomes visible: not only does the invoice look suspicious, but the network around it also does.

![Demo screen: SME invoice upload workflow](TODO)
![Demo screen: financing offers and risk summary](TODO)
![Demo screen: auditor network review](TODO)

## Limitations and next steps

This is a demo-grade product, not a production lender system. The repo explicitly models `GİB`, buyer credit score, bank transfer and e-signature as deterministic mock integrations. The system is intentionally designed to show real anti-fraud logic and local AI controls without sending confidential financial data to a cloud model.

The next step is to move from the mock path to a real policy engine: add live buyer verification, stricter document provenance, human approval workflows and a proper audit ledger outside the demo database. We would also like to add stronger role-based controls and potentially a live model registry so risk models can be versioned and explained in a compliance-ready way.

## Team

- Project: VadeX / Vadesiz
- Repository: https://github.com/omresenn-netizen/hf26-elazig
- License: MIT
- Prize categories entered: Gemma, GitHub Copilot, TabPFN, Entire
- Contributors (placeholders): `@your-dev-username`, `@your-dev-username-2`, `@your-dev-username-3`

## AI disclosure

Most of the code was written with GitHub Copilot agents in VS Code and CLI worktrees. The product itself runs Gemma 4 locally on the machine, and the model is used as a document extractor and risk explainer rather than an autonomous decision-maker. Claude was also used as an assistant for planning, review and some front-end iteration. The result is an AI-assisted project, but the final risk decisions remain in human hands.
