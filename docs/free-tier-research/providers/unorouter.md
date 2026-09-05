---
name: UnoRouter
url: "https://unorouter.com"
setup_instructions: |
  1. Sign up at https://unorouter.com with Discord or GitHub (no credit card required for free models).
  2. Open the Tokens page and create an API key (shown once).
  3. Call the OpenAI-compatible API at https://api.unorouter.com/v1 with the key, using a model ID with the `:free` suffix (e.g. {"model": "gpt-oss-120b:free", ...}).
api_key_url: "https://unorouter.com"
limits:
  requests:
    minute: 1
---

UnoRouter is an open-source OpenRouter alternative: one API key for 300+ models behind an OpenAI-compatible endpoint. It aggregates free lanes from ~18 upstream providers into 190+ `$0`-per-token `:free` model rows behind a single key (homepage shows 217 free of 314+ routable, verified 2026-09-05).

**Free Tier:**

- Any model ID with the `:free` suffix costs $0 per token and never touches the balance; no credit card required (Discord/GitHub signup + key).
- Free tier is best-effort throughput, not guaranteed: each upstream enforces its own RPM/daily quotas, and drained pools return an explicit all-providers-busy 503 until they recover.
- Paid models bill pay-as-you-go from a $1 top-up (credits never expire); paid subscriptions only reduce waiting between free-model requests.

**Free Models (examples observed 2026-09-05; the set shifts as pools drain/recover — resolve live at https://unorouter.com/models filtered for free):**

- [`deepseek-v4-flash:free`](../models/deepseek-v4-flash.md) / [`deepseek-v4-pro:free`](../models/deepseek-v4-pro.md) — DeepSeek.
- `gpt-oss-120b:free` — used in the official quickstart; see [model card](../models/gpt-oss-120b.md) (provider ID has no vendor prefix on UnoRouter).
- [`glm-5.3:free`](../models/glm-5.3.md) / [`glm-5.3-flash:free`](../models/glm-5.3-flash.md) — Z.AI GLM.
- [`gemma-4-31b-it:free`](../models/gemma-4-31b-it.md) — Google Gemma.
- [`qwen-3.8-27b:free`](../models/qwen3.8.md) — Alibaba Qwen.
- `gemini-3.6-flash:free` — Google Gemini.
- `deepseek-reasoner:free` — DeepSeek reasoning.
- [`dots-3-note-preview:free`](../models/dots-3-note.md) — Dots Studio.
- [`nemotron-3.5-lightning:free`](../models/nemotron-3.5-lightning.md) — Nvidia.
- [`agnes-2.0-flash:free`](../models/agnes-flash.md), `aion-3.0-mini:free`, `codestral-latest:free`, `command-r-plus:free` — misc free rows.

**Limits:**

- ~1 request/minute per free model per user (UnoRouter's own fairness cap); hitting it returns HTTP 429 with a `Retry-After` header (frontmatter `minute: 1` is this per-model cap, not account-wide). Upstream RPM caps, daily token budgets (reset midnight UTC), TPM caps, and a per-user concurrency limit apply on top.
- Drained pools return 503 `get_channel_failed` (retryable, recovers in minutes); `model_not_found` means a bad ID (never retry).
- Practical guidance from the provider: rotate across the many free models instead of hammering one.

**Notes:**

- Account required; API key required; no payment for the free tier.
- Endpoints: `/v1/chat/completions`, `/v1/responses`, `/v1/embeddings`, plus Anthropic-native `/v1/messages` and Gemini-native `/v1beta`; base URL `https://api.unorouter.com/v1`.
- Entire stack is public under OSI licenses and self-hostable.
- Data/training policy for free-tier requests: unknown (not documented on pages checked).

**Sources**

- https://unorouter.com/en/docs/platform/errors-and-rate-limits (1 req/min cap, 429/503 semantics verified 2026-09-05)
- https://unorouter.com/en/docs/platform/models-and-pricing (`:free` suffix terms verified 2026-09-05)
- https://unorouter.com/en/docs/platform/quickstart (base URL, key creation, `gpt-oss-120b:free` example verified 2026-09-05)
- https://unorouter.com/en/blog/free-models-aggregated (190+ free rows, 18 upstream providers, 2026-06-15)
- https://unorouter.com/en (homepage counts, Discord/GitHub signup, no card verified 2026-09-05)
- https://unorouter.com/en/models (live free catalog)
