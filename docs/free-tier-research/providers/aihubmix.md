---
name: AIHubMix
url: "https://aihubmix.com"
setup_instructions: |
  1. Create an account at https://aihubmix.com (no credit card required for free models).
  2. Create an API key (AIHUBMIX_API_KEY) in the console.
  3. Call the OpenAI-compatible API at https://api.aihubmix.com/v1 with a `$0/M` model ID.
api_key_url: "https://console.aihubmix.com/statistics"
limits: {}
---

AIHubMix is a gateway over 860+ models with a "56 free models — no credit card required" lane; model pages show $0/M input/output for free rows.

**Free Tier:**

- Free-model lane, no credit card required.
- Free versions are trial-use: limited resources, no stability guarantee, 429s possible under load; production use needs the paid official version of the same model.

**Free Models ($0/M rows observed 2026-09-05, verify live):**

- `hy3-free` — Tencent Hy3, 256K context.
- [`minimax-m3-free`](../models/minimax-m3.md) — MiniMax M3, 1M context.
- `minimax-m2.7-free` — MiniMax M2.7, 196K context.
- `gemini-3.7-flash-free` — Google Gemini 3.7 Flash (trial-use caveat).
- `dots-3-note-preview-free` — Dots Studio 280B MoE preview, 512K context.
- `ox-alpha` — $0 alias row pointing at `glm-5.3-flash`.
- Full lane: https://aihubmix.com/models/free.

**Limits:**

- Published numerics: none; free resources limited, 429 on contention.

**Notes:**

- Account required; API key required; no card for free models.
- Endpoint `https://api.aihubmix.com/v1` is fixture-reported; confirm against https://docs.aihubmix.com before use.

**Sources**

- https://aihubmix.com/pricing (models catalog with $0 rows verified 2026-09-05)
- https://aihubmix.com/models/free
- https://docs.aihubmix.com
