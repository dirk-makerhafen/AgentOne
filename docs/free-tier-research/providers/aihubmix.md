---
name: AIHubMix
url: "https://aihubmix.com"
setup_instructions: |
  1. Create an account at https://aihubmix.com (email or OAuth; no credit card required). Every account starts with 10 trial calls shared across all free models (never expire).
  2. Create an API key on the API Keys page (https://console.aihubmix.com/token); format `sk-...`. One key works for free and paid models.
  3. Call the OpenAI-compatible API at https://aihubmix.com/v1 with a `-free` model ID (e.g. `coding-glm-5.3-free`).
  4. For sustained use: make a one-time top-up of any amount from $1 — the account permanently switches to daily quotas (10 req/min, 100 req/day, 1M tokens/day shared across the free catalog, reset daily). Backup domain if needed: https://api.inferera.com.
api_key_url: "https://console.aihubmix.com/token"
limits:
  requests:
    minute: 10
    day: 100
  tokens:
    day: 1000000
---

AIHubMix is a gateway over 870+ models with a "56 free models — no credit card required" lane; every free model bills $0/M input/output, subsidized by the platform (free page updated 2026-09-04, verified 2026-09-05).

**Free Tier:**

- Before first top-up: 10 trial calls total, shared across all free models, no credit card, never expire. When exhausted the API keeps answering with a trial-used-up note rather than a hard error.
- After a one-time $1+ top-up: permanent daily quotas — 10 requests/min, 100 requests/day, 1M tokens/day shared across the free catalog, reset daily, no expiry. (The top-up is account credit, but sustained daily free use is gated behind this one-time payment — see Notes.)
- Past a cap the API returns 429 until the next minute/day window. Models with a higher request weight count as several requests per call, hence lower caps (see model-specific limits).

**Free Models (56-lane, `-free` IDs; all $0/M observed 2026-09-05, verify live at https://aihubmix.com/models/free):**

- [`minimax-m3-free`](../models/minimax-m3.md) — MiniMax M3, 1M context, 100/day · 10/min.
- [`gemma-4-31b-it-free`](../models/gemma-4-31b-it.md) — Google Gemma 4 31B IT, 262K context, 100/day · 10/min.
- [`laguna-s-2.1-free`](../models/laguna-s-2.1.md) — Poolside Laguna S 2.1, 262K context, 100/day · 10/min each.
- [`laguna-xs-2.1-free`](../models/laguna-xs-2.1.md) — Poolside Laguna XS 2.1, 262K context, 100/day · 10/min each.
- [`nemotron-3-nano-30b-a3b-free`](../models/nemotron-3-nano-30b-a3b.md) — Nvidia Nemotron 3 Nano 30B A3B, 256K context, 100/day · 10/min.
- [`glm-4.7-flash-free`](../models/glm-4.7-flash.md) — Z.AI GLM 4.7 Flash, 100/day · 10/min.
- `hy3-free` — Tencent Hunyuan Hy3, 256K context, 100/day · 10/min.
- [`minimax-m2.7-free`](../models/minimax-m2.7.md) — MiniMax M2.7, 197K context, 100/day · 10/min.
- `gemini-3.7-flash-free` — Google Gemini 3.7 Flash, 1M context, 100/day · 10/min (catalog notes trial-use 429 caveat on this row).
- [`dots-3-note-preview-free`](../models/dots-3-note.md) — Dots Studio 280B MoE preview, 512K context, 100/day · 10/min.
- Most-called this month: `coding-glm-5.3-free`, `coding-glm-5.3-flash-free`, `coding-glm-5.2-free`.
- No `-free` rows observed for `deepseek-v4-flash`, `deepseek-v4-pro`, `glm-4.5-flash`, or `gpt-oss-120b`; [`gpt-oss-20b-free`](../models/gpt-oss-20b.md) exists — see [model card](../models/gpt-oss-20b.md).

**Limits:**

- Documented topped-up quotas (frontmatter): 10 req/min, 100 req/day, 1M tokens/day shared across the free catalog.
- Strictly-free (no top-up): 10 trial calls total, not a rate — see Free Tier.
- Model-specific lower caps (higher request weight): e.g. `gpt-4o-free` / `gpt-4.1-free` 20/day · 2/min; `gemini-3-flash-preview-free` / `gpt-4.1-mini-free` 33/day · 3/min; `gpt-4.1-nano-free` / `coding-glm-5-turbo-free` / `k2.6-code-preview-free` 50/day · 5/min; `gemini-3.1-flash-image-preview-free` 10/day · 1/min.

**Notes:**

- Account required; API key required; no card for the 10 trial calls — but ongoing daily quotas require a one-time $1+ top-up, so sustained use is payment-gated by a minimal top-up rather than purely free. Borderline per the "payment required" exclusion; kept with this explicit flag.
- Trial-use 429 caveats still apply: quota-exceeded calls return 429, and catalog rows (e.g. Gemini 3.7 Flash free version) carry "limited resources, trial use only, 429s possible" notes.
- Correct endpoint is `https://aihubmix.com/v1` (official quickstart, verified 2026-09-05); the fixture-reported `https://api.aihubmix.com/v1` is wrong. Backup domain: `https://api.inferera.com`.
- API key page is https://console.aihubmix.com/token (not /statistics).

**Sources**

- https://aihubmix.com/models/free (56 models, 10 trial calls, $1 top-up → 10/min + 100/day + 1M tokens/day, 429 behavior, updated 2026-09-04, verified 2026-09-05)
- https://docs.aihubmix.com/en/quick-start (endpoint https://aihubmix.com/v1, key page https://aihubmix.com/token verified 2026-09-05)
- https://docs.aihubmix.com/en/blogs/free-ai-models (no card, no trial expiry, RPM + daily token caps verified 2026-09-05)
- https://aihubmix.com/models (56-free-lane banner, per-model trial-use 429 rows verified 2026-09-05)
