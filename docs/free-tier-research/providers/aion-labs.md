---
name: Aion Labs
url: "https://www.aionlabs.ai/"
setup_instructions: |
  1. Sign up at https://www.aionlabs.ai/ (Free tier is the default on signup).
  2. Open the dashboard and go to API Keys.
  3. Generate an API key.
  4. Point any OpenAI-compatible client at base URL https://api.aionlabs.ai/v1 with the key as Bearer token.
api_key_url: "https://www.aionlabs.ai/"
limits:
  requests:
    minute: 15
  tokens:
    minute: 20000
    day: 20000
---

Aion Labs is an independent provider offering its proprietary Aion model family (roleplay/storytelling-specialized) through an OpenAI-compatible REST API at `https://api.aionlabs.ai/v1`.

**Free Tier:**

- **Free Tier:** Recurring free tier, default on signup — a daily credit allowance, $0, no card required (official pricing page).
- Paid tiers 1–5 unlock by lifetime credit top-ups (any top-up, $100, $250, $500, $1,000) and are never reduced.

**Free Models:**

- `aion-labs/aion-2.0` — 128K context, reasoning, max output 32K; DeepSeek V3.2 variant optimized for roleplay/storytelling.
- `aion-labs/aion-3.0` — 128K context, reasoning, max output 32K; GLM-family multi-model system.
- `aion-labs/aion-3.0-mini` — 128K context, reasoning, max output 32K; DeepSeek-family multi-model system.
- `aion-labs/aion-rp-llama-3.1-8b` — 32K context, max output 32K; Llama 3.1 8B roleplay variant (no cached-input price listed).
- Free-tier calls draw from the daily allowance; listed per-token prices ($0.70–$3.00/M input) apply to paid consumption.

**Limits:**

- Free tier (official rate-limits page, quoted exactly): 15 requests/min; 20,000 tokens/min; 20,000 daily token limit.
- Exact size of the daily credit allowance in credits is unpublished — unknown.

**Notes:**

- Account required; API key required for `POST /v1/chat/completions` (`Authorization: Bearer <key>`, `Api-Key` prefix also accepted); `GET /v1/models` is public without auth.
- Payment/billing info: not required for Free tier (official). Phone verification: not required (secondary; official stance unknown).
- Auth: `Authorization: Bearer YOUR_API_KEY` to `https://api.aionlabs.ai/v1`.
- Data-training and region policies: unknown — check Terms/Privacy before sensitive use.
- Secondary sources conflict on OpenAI-compatibility (freellms.org says "No"); official docs state OpenAI-compatible — official wins.

**Sources**

- https://www.aionlabs.ai/docs/
- https://www.aionlabs.ai/pricing/
- https://www.aionlabs.ai/docs/models/
- https://www.aionlabs.ai/docs/rate-limits/
- https://www.aionlabs.ai/docs/quickstart/
- https://www.aionlabs.ai/docs/api-reference/
- https://freellms.org/providers/aion-labs
- https://github.com/nejib1/Free-LLM
