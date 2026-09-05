---
name: FastRouter
url: "https://fastrouter.ai"
setup_instructions: |
  1. Create an account at https://fastrouter.ai and generate a FASTROUTER_API_KEY.
  2. Call the OpenAI-compatible API at https://go.fastrouter.ai/api/v1 with the key.
  3. Use a `:free`-suffixed model ID for the free lane.
api_key_url: "https://fastrouter.ai"
limits: {}
---

FastRouter is an OpenAI-compatible model router whose models directory labels selected models "Free (with limits)".

**Free Tier:**

- Free lane on `:free`-suffixed models; exact free rate limits are unspecified ("with limits").
- Account and API key required; payment requirement for free-lane use: unknown.

**Free Models (verify live in the catalog):**

- `openai/gpt-oss-20b:free` — reasoning/agentic, 131,072 context.
- [`openai/gpt-oss-120b:free`](../models/gpt-oss-120b.md) — reasoning/agentic, 131,072 context.
- Image lane: `flux-schnell`, `seedream-5-lite` listed "Free (with limits)".
- Paid image/video models on the same endpoint (e.g. `gpt-image-2`, `veo`, `seedance`) are NOT free despite zero-cost fixture artifacts elsewhere — trust the official models page.

**Limits:**

- Published numerics: none. "Free (with limits)" only; 429 behavior undocumented.

**Notes:**

- Router/fallback model `fastrouter/auto` bills at the routed model's rate — not free by itself.
- Live catalog with per-model prices: `GET api.fastrouter.ai/api/v1/models` and https://fastrouter.ai/models.

**Sources**

- https://fastrouter.ai/models (free labels verified 2026-09-05)
