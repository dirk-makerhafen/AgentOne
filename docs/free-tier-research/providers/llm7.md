---
name: LLM7.io
url: "https://llm7.io"
setup_instructions: |
  1. Anonymous (lowest limits): no signup — use base URL https://api.llm7.io/v1 with api_key "unused".
  2. For higher free limits: get a free token at https://dash.llm7.io and use it as the API key.
  3. Choose a model via GET https://api.llm7.io/v1/models, or use the "default" / "fast" chat selectors.
api_key_url: "https://dash.llm7.io"
default_api_key: "unused"
limits:
  requests:
    minute: 40
  tokens:
    day: 1000000
---

LLM7.io is an OpenAI-compatible gateway with a permanent two-level free tier: keyless anonymous access and a higher-limit free token; both reach `turbo`-tier models.

**Free Tier:**

- Permanent free tiers, not trial credits: Anonymous (no key) and Free token (from dash.llm7.io); Pro ($12/mo) and topped-up balance unlock `pro`-tier models.
- Frontmatter figures are the Free-token tier; the Anonymous tier is lower (see Limits).

**Free Models:**

- Free tiers reach `turbo`-tier models only; the catalog is live and rotating — resolve IDs via `GET https://api.llm7.io/v1/models` (check the `tier` field) rather than hardcoding.
- `default` — first available general-purpose model selector (chat).
- `fast` — low-latency model selector (chat).
- Secondary-reported concrete IDs (`gpt-oss:20b`, `mistral-Nemo-Instruct-2407`, `minimax-m2.7`) are **unverified; confirm live**.

**Limits:**

- Anonymous: 1 req/sec, 10 req/min, 60 req/hour; 500,000 tokens/24h (input + output).
- Free token: 2 req/sec, 40 req/min, 100 req/hour per the docs limits page; 1,000,000 tokens/24h.
- Self-conflict (verify live before trusting either): the provider homepage currently states Free-token "250 r/h, 60 r/m, and 2 r/s" and Anonymous "60 r/h, 10 r/m" — the per-minute (40 vs 60) and per-hour (100 vs 250) figures disagree between the provider's own docs page and homepage. Frontmatter keeps the docs-page values.
- Pro ($12/mo): 25 req/sec, 1,500 req/min, 15,000 req/hour with a dynamic monthly allowance (see dashboard); overage bills from topped-up balance at live model pricing.
- Image endpoints require a token (no anonymous use); video requests require a token and reserve an async cost hold.

**Notes:**

- Anonymous access needs no account and no real key (`api_key="unused"` placeholder, hence `default_api_key`); free-token signup requirements and phone verification: **unknown**.
- OpenAI-compatible: `https://api.llm7.io/v1` (`/v1/chat/completions`, `/v1/models`, `/v1/images/*`, `/v1/videos`).
- Maximum input size depends on access tier and model context window; Pro allowance subject to capacity, fair use, and abuse-prevention controls.

**Sources**

- https://docs.llm7.io/quickstart
- https://docs.llm7.io/limits
- https://llm7.io/ (homepage rate figures conflict with the docs page — see Limits)
- https://docs.llm7.io/guides/models
- https://docs.llm7.io/guides/models-api
- Secondary (example IDs only): docs/free-tier-research/raw/awesome-free-llm-apis/LLM7.io.json
