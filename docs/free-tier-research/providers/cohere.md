---
name: Cohere
url: "https://cohere.com"
setup_instructions: |
  1. Register for a Cohere account at https://dashboard.cohere.com/welcome/register (no credit card required for trial use).
  2. Go to the API keys page at https://dashboard.cohere.com/api-keys.
  3. Generate a Trial key and copy it.
  4. Call the native API at https://api.cohere.com/v2, or use the OpenAI SDK pointed at https://api.cohere.ai/compatibility/v1 with the Trial key.
api_key_url: "https://dashboard.cohere.com/api-keys"
limits:
  requests:
    minute: 20
    month: 1000
---

Cohere offers free Trial (evaluation) API keys with limited usage across its Chat, Embed, and Rerank APIs.

**Free Tier:**

- Permanent free Trial keys, not expiring trial credits; production keys are paid with much higher limits (verified 2026-09-05).
- Trial keys (and production keys on newer Chat model variants) are limited to 1,000 API calls per month — official rate-limits page (verified 2026-09-05).
- Trial keys are rate-limited and not for production use ("Prod keys work like trial keys for newer model variants ... contact sales@cohere.com").

**Free Models:**

- Exact model IDs confirmed on the official models overview page (verified 2026-09-05): `command-a-plus-05-2026` (128K context, 64K max output, text+images), `command-a-03-2025` (256K context, 8K max output), `command-a-reasoning-08-2025` (256K context, 32K max output), `command-a-translate-08-2025` (8K context, 8K max output), `command-a-vision-07-2025` (128K context, 8K max output), `command-r-plus-08-2024` (128K context, 4K max output), `command-r-08-2024` (128K context, 4K max output), `command-r7b-12-2024` (128K context, 4K max output) — each at 20 req/min on Trial keys per the official rate-limits table.
- `North Mini Code` — listed by display name in the official rate-limits table (20 req/min trial, 500 req/min production); exact versioned API string unconfirmed in official docs, verify in console before publishing it as a model ID.
- Discovery-listed IDs `command-r7b-arabic-02-2025`, `c4ai-aya-expanse-32b`, `c4ai-aya-vision-32b` are secondary-reported, confirm live.
- None of the catalogued model cards is served through this provider — no model-card links apply.

**Limits:**

- Chat API (Trial, per model): 20 req/min; overall Trial cap: 1,000 API calls/month (both official, verified 2026-09-05).
- Other Trial endpoints (official): Embed 2,000 inputs/min; Embed (Images) 5 inputs/min; EmbedJob 5 req/min; Rerank 10 req/min; Tokenize 100 req/min; Audio Transcriptions 5 req/min; Parse 500 req/min; default 500 req/min.
- Production Chat rate for Command A / R+ / R / R7B / North Mini Code: 500 req/min; newer variants (A+, Reasoning, Translate, Vision) have no paid production tier — contact sales@cohere.com.

**Notes:**

- Account required; Trial API key required; no credit card required for trial; phone verification: **unknown** (secondary sources report none required — unverified).
- Endpoints (verified 2026-09-05): native base URL https://api.cohere.com/v2 (`POST /v2/chat`); OpenAI-compatible via https://api.cohere.ai/compatibility/v1 (`POST /chat/completions`).
- "Non-commercial use only" claim from discovery data is **unconfirmed in official docs fetched** — official wording is "not for production use".
- `command-a-03-2025` playground link confirms the exact ID string: https://dashboard.cohere.com/playground?model=command-a-03-2025.

**Sources**

- https://docs.cohere.com/docs/rate-limits (trial/prod limits, 1,000 calls/month — verified 2026-09-05)
- https://docs.cohere.com/docs/models (exact model IDs, context/output — verified 2026-09-05)
- https://docs.cohere.com/docs/compatibility-api (OpenAI-compatible base URL — verified 2026-09-05)
- https://docs.cohere.com/v2/docs/how-does-cohere-pricing-work
- https://cohere.com/pricing
- Secondary (unverified claims only): docs/free-tier-research/raw/awesome-free-llm-apis/Cohere.json
