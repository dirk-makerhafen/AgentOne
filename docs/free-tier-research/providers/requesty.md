---
name: Requesty
url: "https://www.requesty.ai"
setup_instructions: |
  1. Sign up at https://app.requesty.ai/sign-up (Free $0 tier, no credit card required).
  2. Create an API key on the API Keys page (https://app.requesty.ai/api-keys); new accounts include free credits to start routing immediately.
  3. Set base URL to https://router.requesty.ai/v1 in any OpenAI-compatible client.
  4. Call with one of the documented free model IDs; optionally configure a fallback policy to a paid model.
api_key_url: "https://app.requesty.ai/api-keys"
limits:
  requests:
    minute: 20
    day: 200
---

LLM gateway with a rotating selection of $0/token models behind one OpenAI-compatible endpoint.

**Free Tier:**

- Ongoing Free $0 tier ("free for now"; pricing changes announced via changelog ahead of time): access to all free models, 200 requests/day, routing/caching/fallbacks, no credit card required (verified 2026-09-05 on pricing page and free-models doc).
- Frontmatter figures are for new organizations.

**Free Models (per free-models doc, verified 2026-09-05 — all free input/output):**

- [`nvidia/nemotron-3-ultra-550b-a55b`](../models/nemotron-3-ultra-550b-a55b.md) — free input/output.
- [`nvidia/nemotron-3-super-120b-a12b`](../models/nemotron-3-super-120b-a12b.md) — free input/output.
- [`nvidia/nemotron-3-nano-30b-a3b`](../models/nemotron-3-nano-30b-a3b.md) — free input/output.
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` — free input/output.
- [`poolside/laguna-xs.2`](../models/laguna-xs-2.1.md) — free input/output.
- `poolside/laguna-m.1` — free input/output (M-class, no dedicated card).
- [`google/gemma-4-31b-it`](../models/gemma-4-31b-it.md) — free input/output.
- `mistral/leanstral-1-5` — free input/output.
- `nvidia/nemotron-3.5-content-safety` — free input/output (4B guardrail classifier; small specialist, deliberately not catalogued as a model card).

**Limits:**

- New organizations: 200 requests/day + 20 requests/minute, shared across all free models combined. Paying organizations: 1,000/day + 60/minute. Rate-limit errors until the window resets; paid models unaffected.

**Notes:**

- Account required: yes. API key required: yes. Payment/billing info required: no for free models (pricing page: "No credit card required"). Phone verification: unknown.
- Requesty imposes no separate gateway per-minute request limit; it limits concurrent in-flight requests instead, and upstream provider 429s are handled via routing/fallback policies.

**Sources**

- https://docs.requesty.ai/features/free-models (free model table + new/paying-org limits, verified 2026-09-05)
- https://docs.requesty.ai/features/api-limits (spend limits, in-flight model, fallback routing, verified 2026-09-05)
- https://docs.requesty.ai/quickstart (sign-up, API Keys page, `https://router.requesty.ai/v1` endpoint, verified 2026-09-05)
- https://www.requesty.ai/pricing (Free $0 tier: 200 req/day, no credit card, verified 2026-09-05)
- https://docs.requesty.ai/changelog (announced-ahead pricing changes)
- https://www.requesty.ai/models/free (free model library)
