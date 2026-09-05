---
name: DeepSeek V4 Pro
developer: DeepSeek
canonical_id: deepseek/deepseek-v4-pro
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
  - name: Kenari
    file: kenari
    model_id: deepseek-v4-pro:free
    conditions: ":free lane billed Rp 0; free Solo tier (never topped up) is enough; per-minute cap + daily quota tiers, live numbers on kenari.id/plan"
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

DeepSeek V4 Pro is DeepSeek's open-MoE flagship for advanced reasoning, coding, and long agent runs (fixture-reported facts; verify live).

**Capabilities:**

- Reasoning, tool/function calling, structured output, temperature control (fixture-reported).
- Text in / text out; 1M context, up to ~384K output tokens per request (fixture-reported).
- Open weights.

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [UnoRouter](../providers/unorouter.md) | `deepseek-v4-pro:free` | `:free` lane; account + key, no card | ~1 req/min per user + upstream caps | 2026-09-05 |
| [Kenari](../providers/kenari.md) | `deepseek-v4-pro:free` | `:free` lane billed Rp 0; free Solo tier (never topped up) is enough | Per-minute cap per model + daily quota in three tiers (Solo/Payer/Subscription); live numbers on kenari.id/plan | 2026-09-05 |
| [DeepSeek Platform](../providers/deepseek.md) | `deepseek-v4-pro` | No standing free tier; new-user API grant applies generally | Grant terms (one-time, not a quota) | 2026-09-05 |
| [OrcaRouter](../providers/orcarouter.md) | `deepseek/deepseek-v4-pro-free` | Hacker tier free forever, no card; `-free` IDs never touch the wallet | No published numbers — per-workspace per-minute + per-day buckets, tiered by lifetime spend, plus a per-request prompt cap on the lower tier; build for the `429` | 2026-09-05 |

**Notes:**

- Paid reference (for context, not free): ~$0.435/M in / $0.87/M out on DeepSeek's own platform and most gateways.
- Ollama Cloud lists this model in its catalog, but full catalog use requires added credits — not a free row.

**Sources**

- raw/opencode-models-api/unorouter/model_deepseek-v4-pro.json (capabilities/context — discovery data)
- https://unorouter.com/en/models
- https://kenari.id/docs/billing
- https://docs.orcarouter.ai/routing/free-models
