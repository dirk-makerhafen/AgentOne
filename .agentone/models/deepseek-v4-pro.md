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
  input: [text]
  output: [text]
open_weights: true
knowledge_cutoff: "2025-05"
providers:
  - name: UnoRouter
    file: unorouter
    model_id: deepseek-v4-pro:free
    conditions: ":free lane; account + key, no card"
    limits:
      requests:
        minute: 1
    verified: "2026-09-05"
  - name: DeepSeek Platform
    file: deepseek
    model_id: deepseek-v4-pro
    conditions: "No standing free tier; new-user API grant applies generally"
    verified: "2026-09-05"
  - name: OrcaRouter
    file: orcarouter
    model_id: deepseek/deepseek-v4-pro-free
    conditions: "Hacker tier free forever, no card; `-free` IDs never touch the wallet; free set rotates, catalog is source of truth"
    verified: "2026-09-05"
---

DeepSeek V4 Pro is DeepSeek's open-weight flagship (released 2026-04-24; GA checkpoint V4-Pro-0813 on 2026-08-13): a 1.6T-total / 49B-active MoE with 1M context and up to ~384K output, MIT-licensed weights, for advanced reasoning, coding, and long agent runs.

**Capabilities:**

- Reasoning (non-thinking / high / max effort modes), tool/function calling, structured output, temperature control (official API docs; fixture-consistent).
- Text in / text out only; 1M context, up to ~384K output tokens per request.
- Open weights under MIT (weights on Hugging Face; ~865 GB on disk — cluster-scale to self-host).

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [UnoRouter](../providers/unorouter.md) | `deepseek-v4-pro:free` | `:free` lane; account + key, no card | ~1 req/min per user + upstream caps | 2026-09-05 |
| [DeepSeek Platform](../providers/deepseek.md) | `deepseek-v4-pro` | No standing free tier; new-user API grant applies generally | Grant terms (one-time, not a quota) | 2026-09-05 |
| [OrcaRouter](../providers/orcarouter.md) | `deepseek/deepseek-v4-pro-free` | Hacker tier free forever, no card; `-free` IDs never touch the wallet | No published numbers — per-workspace per-minute + per-day buckets, tiered by lifetime spend, plus a per-request prompt cap on the lower tier; build for the `429` | 2026-09-05 |

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
