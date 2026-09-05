---
name: DeepSeek V4 Flash
developer: DeepSeek
canonical_id: deepseek/deepseek-v4-flash
family: deepseek-flash
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
    model_id: deepseek-v4-flash:free
    conditions: ":free lane; account + key, no card"
    limits:
      requests:
        minute: 1
    verified: "2026-09-05"
  - name: Kenari
    file: kenari
    model_id: deepseek-v4-flash:free
    conditions: ":free lane billed Rp 0; free Solo tier (never topped up) is enough; per-minute cap + daily quota tiers, live numbers on kenari.id/plan"
    verified: "2026-09-05"
  - name: DeepSeek Platform
    file: deepseek
    model_id: deepseek-v4-flash
    conditions: "No standing free tier; new-user API grant applies generally"
    verified: "2026-09-05"
---

DeepSeek V4 Flash is DeepSeek's fast, economical reasoning lane for coding and long-context work (fixture-reported facts; verify live).

**Capabilities:**

- Reasoning, tool/function calling, structured output, temperature control (fixture-reported).
- Text in / text out; 1M context, up to 384K output tokens per request (fixture-reported).
- Open weights.

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [UnoRouter](../providers/unorouter.md) | `deepseek-v4-flash:free` | `:free` lane; account + key, no card | ~1 req/min per user + upstream caps | 2026-09-05 |
| [Kenari](../providers/kenari.md) | `deepseek-v4-flash:free` | `:free` lane billed Rp 0; free Solo tier (never topped up) is enough | Per-minute cap per model + daily quota in three tiers (Solo/Payer/Subscription); live numbers on kenari.id/plan | 2026-09-05 |
| [DeepSeek Platform](../providers/deepseek.md) | `deepseek-v4-flash` | No standing free tier; new-user API grant applies generally | Grant terms (one-time, not a quota) | 2026-09-05 |

**Notes:**

- Cloudflare Workers AI fixture rows (`@cf/deepseek-ai/deepseek-v4-flash-0731`) are absent from the current limits page — unverified whether still gated, renamed, or removed.
- Ollama Cloud lists this model in its catalog, but full catalog use requires added credits — not a free row.

**Sources**

- raw/opencode-models-api/unorouter/model_deepseek-v4-flash:free.json (capabilities/context — discovery data)
- https://unorouter.com/en/models
- https://kenari.id/docs/billing
