---
name: LLM7.io
url: "https://llm7.io"
api_base: "https://api.llm7.io/v1"
setup_instructions: |
  1. Anonymous (lowest limits): no signup — use base URL https://api.llm7.io/v1 with api_key "unused" (per the official quickstart, verified 2026-09-05).
  2. For higher free limits: get a free token at https://dash.llm7.io and use it as the API key.
  3. Choose a model via GET https://api.llm7.io/v1/models (check the `tier` field: `turbo` = reachable on free tiers, `pro` = paid), or use the "default" / "fast" chat selectors.
api_key_url: "https://dash.llm7.io"
default_api_key: "unused"
limits:
  requests:
    second: 2
    minute: 60
    hour: 250
  tokens:
    day: 1000000
---

LLM7.io is an OpenAI-compatible gateway with a permanent two-level free tier: keyless anonymous access and a higher-limit free token; both reach `turbo`-tier models.

**Free Tier:**

- Permanent free tiers, not trial credits: Anonymous (no key) and Free token (from dash.llm7.io); Pro ($12/mo) and topped-up balance unlock `pro`-tier models.
- Frontmatter figures are the Free-token tier; the Anonymous tier is lower (see Limits).

**Free Models:**

- Free tiers reach `turbo`-tier models only; the catalog is live and rotating — resolve IDs via `GET https://api.llm7.io/v1/models` (check the `tier` field) rather than hardcoding.
- Live-verified `turbo` (free) chat IDs on 2026-09-05 (46-model catalog queried directly): `codestral-latest`, [`gemma4:31b`](../models/gemma-4-31b-it.md) (provider ID differs from card default), `gpt-oss`, [`minimax-m2.7`](../models/minimax-m2.7.md), `mistral-Nemo-Instruct-2407`.
- `default` — first available general-purpose model selector (chat).
- `fast` — low-latency model selector (chat).
- Currently `pro`-tier (NOT free, verified live 2026-09-05): `deepseek-v4-flash`, `deepseek-v4-flash:0731`, `deepseek-v4-pro`, `gemini-3-flash`, `glm-5.3`, `glm-5.3-flash`, `gpt-5.4`, `kimi-k3`, among others. None of the other `pro`-tier IDs above has a model card row, so no other card links apply. Of the live `turbo` IDs, `gemma4:31b` is claimed by [gemma-4-31b-it](../models/gemma-4-31b-it.md) and `minimax-m2.7` by [minimax-m2.7](../models/minimax-m2.7.md).

**Limits:**

- Anonymous: 1 req/sec, 10 req/min, 60 req/hour; 500,000 tokens/24h (input + output) — consistent across the docs limits page, homepage, and Terms (verified 2026-09-05).
- Free token: 2 req/sec, 60 req/min, 250 req/hour per the homepage and the Terms of Service (last updated 2026-08-09); 1,000,000 tokens/24h rolling window (verified 2026-09-05).
- Self-conflict, updated 2026-09-05: the docs limits page still states Free-token "40 req/min, 100 req/hour", disagreeing with the homepage ("60 r/m, 250 r/h") and the Terms ("60 text requests/min, 250 text requests/hour"). Frontmatter follows the homepage + Terms (two agreeing sources, Terms dated 2026-08-09); re-check `GET /v1/models` docs and the live docs page before trusting either.
- Pro ($12/mo): 25 req/sec, 1,500 req/min, 15,000 req/hour with a dynamic monthly allowance (see dashboard); overage bills from topped-up balance at live model pricing.
- Image endpoints require a token (no anonymous use); video requests require a token and reserve an async cost hold.

**Notes:**

- Anonymous access needs no account and no real key (`api_key="unused"` placeholder, hence `default_api_key`); free-token signup requirements and phone verification: **unknown**.
- OpenAI-compatible: `https://api.llm7.io/v1` (`/v1/chat/completions`, `/v1/models`, `/v1/images/*`, `/v1/videos`) (verified live 2026-09-05 — `/v1/models` returns the 46-model catalog).
- Maximum input size depends on access tier and model context window; Pro allowance subject to capacity, fair use, and abuse-prevention controls.

**Sources**

- https://docs.llm7.io/limits (rate/token tables)
- https://docs.llm7.io/quickstart (`api_key="unused"` anonymous setup — verified 2026-09-05)
- https://docs.llm7.io/guides/models-api (`turbo` vs `pro` tier semantics)
- https://llm7.io/ (Free-token 250 r/h, 60 r/m, 2 r/s; Anonymous 60 r/h, 10 r/m — verified 2026-09-05)
- https://github.com/chigwell/llm7.io/blob/main/TERMS.md (Terms, last updated 2026-08-09: tier quotas)
- https://api.llm7.io/v1/models (live catalog queried 2026-09-05: 46 models, turbo IDs listed above)
- Secondary (example IDs only): docs/free-tier-research/raw/awesome-free-llm-apis/LLM7.io.json
