---
name: SambaNova Cloud
url: "https://cloud.sambanova.ai"
setup_instructions: |
  1. Create an account at https://cloud.sambanova.ai (no payment method required for the free tier).
  2. Open the APIs page and create an API key.
  3. Call the OpenAI-compatible API at https://api.sambanova.ai/v1 with the key as Bearer token and a free-tier model ID.
api_key_url: "https://cloud.sambanova.ai"
limits:
  requests:
    minute: 20
    day: 20
  tokens:
    day: 200000
---

SambaNova Cloud hosts fast inference for open and partner models. Accounts with no payment method linked get a standing free tier of 20 RPM / 20 RPD / 200,000 TPD per model.

**Free Tier:**

- Standing free tier, not a trial: applies automatically when no payment method is linked. Linking a card moves the account to the higher Developer tier.
- No credit card and no phone verification required for the free tier.

**Free Models:**

- `DeepSeek-V3.1` — reasoning, free-tier limits apply.
- `DeepSeek-V3.2` (preview) — reasoning, free-tier limits apply.
- `Meta-Llama-3.3-70B-Instruct` — chat, free-tier limits apply.
- `gpt-oss-120b` — reasoning/agentic, free-tier limits apply.
- `gemma-4-31B-it` (preview) — chat, free-tier limits apply.
- Preview models can change or be removed; confirm the live catalog before use.

**Limits:**

- Per model, per account (not per key): 20 requests/min, 20 requests/day, 200,000 tokens/day.
- Daily window resets on a fixed daily window, not exactly 24h after exhaustion.
- Context range around 128K on free models (verify per model live).

**Notes:**

- Account required; API key required; payment method must NOT be linked (linking one ends free-tier rates).
- OpenAI-compatible: `https://api.sambanova.ai/v1` (`/v1/chat/completions`).
- Commercial-use license under SambaCloud ToS (no evaluation-only clause reported).

**Sources**

- https://docs.sambanova.ai/docs/en/models/rate-limits (free-tier table; page blocks some fetches — re-check live)
- https://cloud.sambanova.ai/plans
- Secondary (setup/endpoint corroboration): https://freellm.net/providers/sambanova, https://freellmapihub.com/p/sambanova
