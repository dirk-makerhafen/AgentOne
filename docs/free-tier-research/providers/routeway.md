---
name: Routeway
url: "https://routeway.ai"
api_base: "https://api.routeway.ai/v1"
setup_instructions: |
  1. Sign up at https://routeway.ai/dashboard on the Starter plan.
  2. Open Dashboard -> API Keys and create an API key (`sk-...`).
  3. Point an OpenAI-compatible client at https://api.routeway.ai/v1 and call a model id ending in `:free`.
api_key_url: "https://routeway.ai/dashboard/keys"
limits:
  requests:
    minute: 20
    day: 200
---

Routeway is an OpenAI-compatible model gateway with a standing zero-cost `:free` route lane. The official FAQ caps free routes at 20 requests/minute and 200 requests/day (UTC midnight reset); the cap cannot be raised. Free routes are lower-priority and documented as development/testing only, with no SLA.

**Free Tier:**

- Standing `:free` lane: 20 RPM / 200 RPD (official FAQ, verified 2026-11-20).
- Account + API key required. Official docs state a payment method is required only before using paid/PAYG models; whether a card must be on file to obtain a free key is **unverified**.
- Dropping the `:free` suffix selects the paid model.

**Free Models:**

- All ids ending in `:free` are the zero-cost lane. The official cheapest-model page currently lists "Glimmer 30B (Free)", "MiniMax M3.1 Flash (Free)", "DeepSeek V4.1 Flash 1017 (Free)" and several "Gemma 4 26B ... (Free)" variants.
- Catalog-reported wire ids, to confirm via authenticated `GET /v1/models`: `muse-glimmer-30b:free`, `gemma-4-26b-a4b-it-{chimerax,darksoul,luminous,moonlight,musica,meromero}:free`. These are leads, not independently verified ids.
- Official tags mark the listed free routes with Function Calling and Reasoning; the catalog's capability flags for the Gemma variants conflict and appear stale.

**Limits:**

- 20 requests/minute and 200 requests/day for free routes (provider-wide frontmatter values).
- Catalog reports 5 RPM for `muse-glimmer-30b:free`; treat as an observed lead, not the documented cap.

**Notes:**

- Capabilities are exposed per model in `GET /v1/models`.
- freeLLMAPI reports a browser-style `User-Agent` requirement (non-browser clients can receive Cloudflare 1010) and observed ~5 RPM despite the documented 20 RPM; both are secondary, not official.
- The API also exposes `/v1/responses` and `/v1/messages`, but the zero-cost lane was verified only against the OpenAI-compatible surface.

**Sources**

- https://routeway.ai/
- https://routeway.ai/models/cheapest
- https://docs.routeway.ai/getting-started/faq
- https://docs.routeway.ai/api-reference/overview
- docs/free-tier-research/raw/freellmapi-catalog/platforms/routeway.json (discovery lead, verified 2026-11-20)
