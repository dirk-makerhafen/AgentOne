---
name: DeepSeek V4 Pro
developer: DeepSeek
canonical_id: deepseek/deepseek-v4-pro
leaderboard_id: deepseek-v4-pro
leaderboard_rank: 19
family: deepseek-thinking
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

DeepSeek V4 Pro is DeepSeek's open-weight flagship (released 2026-04-24; GA checkpoint V4-Pro-0813 on 2026-08-13): a 1.6T-total / 49B-active MoE with 1M context and up to ~384K output, MIT-licensed weights, for advanced reasoning, coding, and long agent runs.

**Capabilities:**

- Reasoning (non-thinking / high / max effort modes), tool/function calling, structured output, temperature control (official API docs; fixture-consistent).
- Text in / text out only; 1M context, up to ~384K output tokens per request.
- Open weights under MIT (weights on Hugging Face; ~865 GB on disk — cluster-scale to self-host).

**Notes:**

- Kenari fixture rows (`deepseek-v4-pro:free`) are absent from the live catalog as of 2026-09-05 — re-check `GET /v1/models` before use.
- Paid reference (for context, not free): ~$0.435/M in / $0.87/M out on DeepSeek's own platform and most gateways.
- Ollama Cloud lists this model in its catalog, but full catalog use requires added credits — not a free row.
- Skipped leads: SiliconFlow lists `deepseek-ai/DeepSeek-V4-Pro` but fixtures report nonzero prices — treated as paid per its provider file. LLM7's `deepseek-v4-pro` is `pro`-tier (paid), not `turbo` — not free. StreamLake Vanchin maps base models to per-user endpoint IDs with login-gated eligibility — no 1:1 free ID assertable. Pollinations' `deepseek-pro` matches no card ID exactly — not claimed.

**Sources**

- https://api-docs.deepseek.com/news/news260424/ (official: 2026-04-24 release, 1.6T/49B, 1M context, MIT; GA 0813 checkpoint 2026-08-13)
- raw/opencode-models-api/unorouter/model_deepseek-v4-pro.json (capabilities/context — discovery data)
- https://unorouter.com/en/models
- https://kenari.id/docs/billing
- https://docs.orcarouter.ai/routing/free-models
