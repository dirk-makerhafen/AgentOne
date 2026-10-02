---
name: SambaNova Cloud
url: "https://cloud.sambanova.ai"
api_base: "https://api.sambanova.ai/v1"
setup_instructions: |
  1. Create an account at https://cloud.sambanova.ai (free tier applies when no payment method is linked).
  2. Open the API section (APIs page) and generate an API key (up to 25 keys; save it — it cannot be viewed again).
  3. Call the OpenAI-compatible API at https://api.sambanova.ai/v1 with the key as Bearer token and a free-tier model ID.
api_key_url: "https://cloud.sambanova.ai/apis"
limits:
  requests:
    minute: 20
    day: 20
  tokens:
    day: 200000
---

SambaNova Cloud hosts fast inference for open and partner models on RDU hardware. Accounts with no payment method linked get a standing free tier of 20 RPM / 20 RPD / 200,000 TPD per model.

**Free Tier:**

- Standing free tier, not a trial: applies automatically when no payment method is linked. Linking a card moves the account to the higher Developer tier (capped at 20M tokens/day across all models).
- No credit card required for the free tier (official: tier is defined by absence of a linked payment method). Phone verification: unverified in official docs.
- Re-verified 2026-09-05 against the official rate-limits page.

**Free Models:**

- `DeepSeek-V3.1` — reasoning, free-tier limits apply.
- `DeepSeek-V3.2` (preview) — reasoning/evaluation only, free-tier limits apply; preview models may be removed at short notice.
- `Meta-Llama-3.3-70B-Instruct` — chat, free-tier limits apply.
- [`gpt-oss-120b`](../models/gpt-oss-120b.md) — reasoning/agentic, free-tier limits apply.
- [`gemma-4-31B-it`](../models/gemma-4-31b-it.md) (preview) — chat, free-tier limits apply; preview models may be removed at short notice.
- Confirm the live catalog before use; Developer-tier RPD/RPM are higher (e.g. 60 RPM / 12,000 RPD on DeepSeek-V3.1, gpt-oss-120b, gemma-4-31B-it; 240 RPM / 48,000 RPD on Llama-3.3-70B).

**Limits:**

- Per model, per account (not per key): 20 requests/min, 20 requests/day, 200,000 tokens/day — identical across all five free models, so frontmatter carries them provider-wide.
- Daily window resets on a fixed daily window, not exactly 24h after exhaustion.
- Rate-limit status headers on every response (`x-ratelimit-limit-requests`, `x-ratelimit-remaining-requests-day`, etc.).

**Notes:**

- Account required; API key required; payment method must NOT be linked (linking one ends free-tier rates).
- OpenAI-compatible: `https://api.sambanova.ai/v1` (`/v1/chat/completions`).
- Context windows not stated on the rate-limits page — verify per model live.

**Sources**

- https://docs.sambanova.ai/docs/en/models/rate-limits
- https://docs.sambanova.ai/docs/en/get-started/api-keys-urls
- https://docs.sambanova.ai/docs/en/get-started/quickstart
- https://cloud.sambanova.ai/plans
