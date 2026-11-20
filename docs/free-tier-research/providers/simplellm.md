---
name: SimpleLLM
url: "https://simplellm.eu"
api_base: "https://api.simplellm.eu/v1"
setup_instructions: |
  1. Sign up at https://app.simplellm.eu/signup (no card) and create an API key in the dashboard.
  2. Point an OpenAI-compatible client at https://api.simplellm.eu/v1.
  3. Use `free-gemma-4-E4B` or `free-Llama-3.1-8B-Instruct`.
  4. Read GET /v1/rate-limit for the account's current hourly/daily buckets.
api_key_url: "https://app.simplellm.eu/signup"
---

SimpleLLM is a European OpenAI-compatible gateway with two permanently zero-priced models. Account + key required, no payment. Verified 2026-11-20.

**Free Tier:**

- Only **one free-model request in flight per account**, shared across all free models and all keys (streaming and non-streaming). Extra requests get `429 free_model_concurrency_limit` with `Retry-After: 1`; `503 free_concurrency_unavailable` if the limiter is down.
- Hourly/daily request and token buckets exist (`limit_rph/rpd/tph/tpd`) but are account-specific and not published as a fixed table. Read `GET /v1/rate-limit`.
- Catalog-reported numbers (100 req/hour, 1,000/day, 50K tokens/hour, 500K/day) are **not officially documented** and are omitted from frontmatter.

**Free Models:**

- `free-Llama-3.1-8B-Instruct` — `is_free: true`, enabled, 131,072 context, zero input/output price; text model, tool calls mentioned in description, no vision.
- `free-gemma-4-E4B` — `is_free: true`, enabled, 50,000 context, zero price; compact text model. The paid `gemma-4-E4B` alias has 131,072 context — do not mix them.
- Disabled/planned free entries (`kode-14b`, `Mistral-7B-Instruct-v0.3`) are not currently usable.

**Limits:**

- No fixed numerics in frontmatter: the only published hard rule is one concurrent free-model request per account.

**Notes:**

- `free-*` aliases are capped variants of the same underlying models; context differs from standard aliases.
- Docs warn a listed alias can point to a disabled backend.
- GTC reserves the right to restrict free-model availability.

**Sources**

- https://simplellm.eu/api/models
- https://simplellm.eu/docs/models.md
- https://simplellm.eu/docs/limits.md
- https://simplellm.eu/docs/authentication.md
- https://simplellm.eu/agb
- docs/free-tier-research/raw/freellmapi-catalog/platforms/simplellm.json (discovery lead, verified 2026-11-20)
