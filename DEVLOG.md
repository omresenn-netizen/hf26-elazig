# Dev Log – Hacktoberfest Elazığ, 17–18 Oct 2026

Short notes as we go. Becomes the source for the DEV post.

## 17 Oct

- **Setup:** Ollama + `gemma4` (7.5B, Q4_K_M, vision/audio/tools, Apache 2.0) on an RTX 4070 Laptop GPU.
  First call 64 s (model load), warm calls ~2.5 s. 100% GPU.
- **First test:** Gemma turned a free-form Turkish sentence into clean JSON on the first try.
- **Tools:** GitHub Copilot (VS Code, Agent mode) writes the code. Copilot chat sessions exported to `sessions/`.
