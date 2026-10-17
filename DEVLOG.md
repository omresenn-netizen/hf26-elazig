# Dev Log – Hacktoberfest Elazığ, 17–18 Oct 2026

Short notes as we go. Becomes the source for the DEV post.

## 17 Oct

- **Setup:** Ollama + `gemma4` (7.5B, Q4_K_M, vision/audio/tools, Apache 2.0) on an RTX 4070 Laptop GPU.
  First call 64 s (model load), warm calls ~2.5 s. 100% GPU.
- **First test:** Gemma turned a free-form Turkish sentence into clean JSON on the first try.
- **Tools:** GitHub Copilot (VS Code, Agent mode) writes the code. Copilot chat sessions exported to `sessions/`.
- **Copilot ↔ Ollama:** gemma4 added as a model in Copilot Chat (Ollama provider) – Copilot can talk to the same local model.

## 18 Oct

- **Idea picked: Vadesiz.** Started from a real phone call: someone asked a family member to issue a
  200k TL invoice for a commission – a textbook "naylon fatura". The same cash crunch that drives
  people to fake invoices is what invoice financing solves legally.
- **Demo data:** 15 fictional companies, 47 invoices: 30 legit, a 3-company circular ring,
  an invoice broker, a sector mismatch, a capacity outlier, an unapproved and a duplicate invoice.
- **Gemma reads invoices:** first try on a generated e-Fatura image returned every field correctly
  (seller, buyer, VKN, items, KDV, total, missing delivery note) in 26 s.
