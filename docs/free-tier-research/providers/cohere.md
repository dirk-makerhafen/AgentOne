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
---

Cohere offers free Trial (evaluation) API keys with limited usage across its Chat, Embed, and Rerank APIs.

**Free Tier:**

- Permanent free Trial keys, not expiring trial credits; production keys are paid with much higher limits.
- Trial keys (and production keys on newer Chat model variants) are limited to 1,000 API calls per month.
- Trial keys are rate-limited and not for production/commercial use. The discovery-fixture cost-0 row for `north-mini-code-1-0` mirrors trial-key $0, not a free production model — the exact API string `north-mini-code-1-0` is unconfirmed verbatim in official docs; verify in console before publishing it as a model ID.

**Free Models:**

- Command A+, Command A Reasoning, Command A Translate, Command A Vision, Command A, Command R+, Command R, Command R7B, North Mini Code — each at 20 req/min on Trial keys (per official rate-limits table; exact versioned IDs such as `command-a-03-2025` are secondary-reported, confirm live).
- Trial limits also documented for Embed, Embed (Images), EmbedJob, Rerank, Tokenize, Audio Transcriptions, and Parse endpoints.

**Limits:**

- Chat API (Trial, per model): 20 req/min; overall Trial cap: 1,000 API calls/month.
- Other Trial endpoints: Embed 2,000 inputs/min; Embed (Images) 5 inputs/min; EmbedJob 5 req/min; Rerank 10 req/min; Tokenize 100 req/min; Audio Transcriptions 5 req/min; Parse 500 req/min; default 500 req/min.
- Production Chat rate for Command A / R+ / R / R7B / North Mini Code: 500 req/min.

**Notes:**

- Account required; Trial API key required; no credit card required for trial; phone verification: **unknown** (secondary source reports none required).
- OpenAI-compatible via https://api.cohere.ai/compatibility/v1; native base URL https://api.cohere.com/v2.
- Newer variants (Command A Reasoning, A Translate, A Vision, A+) have no paid production tier — production keys behave like trial keys; contact sales@cohere.com for production use.
- "Non-commercial use only" claim from discovery data is **unconfirmed in official docs fetched**.

**Sources**

- https://docs.cohere.com/docs/rate-limits
- https://docs.cohere.com/v2/docs/how-does-cohere-pricing-work
- https://docs.cohere.com/docs/compatibility-api
- https://cohere.com/pricing
- Secondary: docs/free-tier-research/raw/awesome-free-llm-apis/Cohere.json; https://freellm.net/providers/cohere (no-card/no-phone claim, unverified)
