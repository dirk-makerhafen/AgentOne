---
name: DeepSeek V4 Flash
developer: DeepSeek
canonical_id: deepseek/deepseek-v4-flash
leaderboard_id: deepseek-v4-flash
leaderboard_rank: 53
family: deepseek-flash
context_window: 1000000
max_output_tokens: 384000
reasoning: true
tool_call: true
structured_output: true
temperature: true
modalities:
  input:
  - text
  output:
  - text
open_weights: true
knowledge_cutoff: 2025-05
---

DeepSeek V4 Flash is DeepSeek's cost-optimized open-weight reasoning lane (released 2026-04-24; 0731 checkpoint 2026-07-31): a 284B-total / 13B-active MoE with 1M context and up to 384K output, MIT-licensed weights, for coding and long-context work.

**Capabilities:**

- Reasoning (non-thinking / high / max effort modes), tool/function calling, structured output, temperature control (official API docs; fixture-consistent).
- Text in / text out only — rumored vision modes did not ship; 1M context, up to 384K output tokens per request.
- Open weights under MIT (weights on Hugging Face; ~160 GB on disk).

**Notes:**

- Kenari fixture rows (`deepseek-v4-flash:free`) are absent from the live catalog as of 2026-09-05 — re-check `GET /v1/models` before use.
- Cloudflare Workers AI fixture rows (`@cf/deepseek-ai/deepseek-v4-flash-0731`) are confirmed paid-gated on the current pricing page (updated 2026-08-28) — not a free row.
- Ollama Cloud lists this model in its catalog, but full catalog use requires added credits — not a free row.
- Skipped leads: SiliconFlow lists `deepseek-ai/DeepSeek-V4-Flash` but fixtures report nonzero prices — treated as paid per its provider file. InferX's `deepseek-v4-flash-0731` is 70% off (paid), not $0 — excluded per its provider file. LLM7's `deepseek-v4-flash` / `deepseek-v4-flash:0731` are `pro`-tier (paid), not `turbo` — not free. StreamLake Vanchin maps base models to per-user endpoint IDs with login-gated eligibility — no 1:1 free ID assertable. Pollinations' `deepseek`, `deepseek-pro`, and `deepseek/deepseek-v4-flash-vision-exp` match no card ID exactly and the vision-exp row is plausibly a different (multimodal) variant — not claimed.

**Sources**

- https://api-docs.deepseek.com/news/news260424/ (official: 2026-04-24 release, 284B/13B, 1M context, MIT)
- raw/opencode-models-api/unorouter/model_deepseek-v4-flash:free.json (capabilities/context — discovery data)
- https://unorouter.com/en/models
- https://kenari.id/docs/billing
- https://docs.orcarouter.ai/routing/free-models
