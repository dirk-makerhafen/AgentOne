---
name: UnoRouter
url: https://unorouter.com
api_base: https://api.unorouter.com/v1
setup_instructions: '1. Sign up at https://unorouter.com with Discord or GitHub (no
  credit card required for free models).

  2. Open the Tokens page and create an API key (shown once).

  3. Call the OpenAI-compatible API at https://api.unorouter.com/v1 with the key,
  using a model ID with the `:free` suffix (e.g. {"model": "gpt-oss-120b:free", ...}).

  '
api_key_url: https://unorouter.com
---

UnoRouter is an open-source OpenRouter alternative: one API key for 300+ models behind an OpenAI-compatible endpoint. It aggregates free lanes from ~18 upstream providers into 190+ `$0`-per-token `:free` model rows behind a single key (homepage shows 217 free of 314+ routable, verified 2026-09-05).

**Sources**

- https://unorouter.com/en/docs/platform/errors-and-rate-limits (1 req/min cap, 429/503 semantics verified 2026-09-05)
- https://unorouter.com/en/docs/platform/models-and-pricing (`:free` suffix terms verified 2026-09-05)
- https://unorouter.com/en/docs/platform/quickstart (base URL, key creation, `gpt-oss-120b:free` example verified 2026-09-05)
- https://unorouter.com/en/blog/free-models-aggregated (190+ free rows, 18 upstream providers, 2026-06-15)
- https://unorouter.com/en (homepage counts, Discord/GitHub signup, no card verified 2026-09-05)
- https://unorouter.com/en/models (live free catalog)
