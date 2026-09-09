---
name: Aion Labs
url: "https://www.aionlabs.ai/"
api_base: "https://api.aionlabs.ai/v1"
setup_instructions: |
  1. Sign up at https://www.aionlabs.ai/accounts/signup/ (Free tier is the default on signup, $0, no card required).
  2. Open the dashboard and create an API key at API Keys (https://www.aionlabs.ai/app/api-keys/).
  3. Point any OpenAI-compatible client at base URL https://api.aionlabs.ai/v1 with the key as Bearer token (`Authorization: Bearer YOUR_API_KEY`; the `Api-Key` header prefix is also accepted).
  4. Call `POST /v1/chat/completions` (or `POST /v1/responses`) with an `aion-labs/` model ID. `GET /v1/models` needs no auth.
api_key_url: "https://www.aionlabs.ai/app/api-keys/"
limits:
  requests:
    minute: 15
  tokens:
    minute: 20000
    day: 20000
---

Aion Labs is an independent provider offering its proprietary Aion model family (roleplay/storytelling-specialized) through an OpenAI-compatible REST API at `https://api.aionlabs.ai/v1`. All claims below re-verified against official docs 2026-09-05.

**Free Tier:**

- **Free Tier:** Recurring free tier, default on signup — a daily credit allowance, $0, no card required (official pricing page).
- Paid tiers 1–5 unlock by lifetime credit top-ups (any top-up, $100, $250, $500, $1,000) and are never reduced.

**Free Models:**

All 4 catalog models are usable on the Free tier, drawing from the daily credit allowance (per-token prices below apply to paid consumption):

- `aion-labs/aion-2.0` — 128K context (131072), max output 32K, reasoning (`reasoning_effort` none/low/medium/high, default medium); DeepSeek V3.2 variant optimized for roleplay/storytelling. $0.80 in / $0.20 cached / $1.60 out per 1M.
- `aion-labs/aion-3.0` — 128K context, max output 32K, reasoning; GLM-family multi-model system. $3.00 in / $0.75 cached / $6.00 out per 1M.
- `aion-labs/aion-3.0-mini` — 128K context, max output 32K, reasoning; DeepSeek-family multi-model system. $0.70 in / $0.18 cached / $1.40 out per 1M.
- `aion-labs/aion-rp-llama-3.1-8b` — 32K context, max output 32K (no reasoning flag); Llama 3.1 8B roleplay variant. $0.80 in / no cached price / $1.60 out per 1M.
- API supports streaming (SSE), OpenAI-format tool calls, and an alternative `POST /v1/responses` endpoint (official API reference).

**Limits:**

- Free tier (official rate-limits page, quoted exactly, re-verified 2026-09-05): 15 requests/min; 20,000 tokens/min; 20,000 daily token limit.
- Exact size of the daily credit allowance in credits is unpublished — unknown.

**Notes:**

- Account required; API key required for all endpoints except `GET /v1/models` (public without auth).
- Payment/billing info: not required for Free tier (official pricing page). Phone verification: not required (secondary; official stance unknown).
- Keys are issued and revoked in the dashboard; `GET /v1/models` lists the current catalog without auth.
- Data-training and region policies: unknown — check Terms/Privacy before sensitive use.
- Secondary sources conflict on OpenAI-compatibility (freellms.org says "No"); official docs state OpenAI-compatible — official wins.

**Sources**

- https://www.aionlabs.ai/docs/ (OpenAI-compatible API)
- https://www.aionlabs.ai/pricing/ (Free tier $0, daily credit allowance, no card)
- https://www.aionlabs.ai/docs/models/ (model list, context, prices, release dates)
- https://www.aionlabs.ai/docs/rate-limits/ (tier table: Free 15 RPM / 20K TPM / 20K daily)
- https://www.aionlabs.ai/docs/quickstart/ (dashboard key creation, base URL, Bearer auth)
- https://www.aionlabs.ai/docs/api-reference/ (auth rules incl. `Api-Key` prefix, endpoints, reasoning params)
- https://freellms.org/providers/aion-labs
- https://github.com/nejib1/Free-LLM
