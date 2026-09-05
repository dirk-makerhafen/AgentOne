---
name: Requesty
url: "https://www.requesty.ai"
setup_instructions: |
  1. Sign up for a Requesty account (no credit card required for free models).
  2. Generate an API key in the Requesty Console (API Keys page).
  3. Set base URL to https://router.requesty.ai/v1 in any OpenAI-compatible client.
  4. Call with one of the documented free model IDs; optionally configure a fallback policy to a paid model.
api_key_url: "https://app.requesty.ai/"
limits:
  requests:
    minute: 20
    day: 200
---

LLM gateway with a rotating selection of $0/token models behind one OpenAI-compatible endpoint.

**Free Tier:**

- Ongoing free-models tier ("free for now"; pricing changes announced via changelog ahead of time). Frontmatter figures are for new organizations.

**Free Models:**

- `nvidia/nemotron-3-ultra-550b-a55b` — free input/output.
- `nvidia/nemotron-3-super-120b-a12b` — free input/output.
- `nvidia/nemotron-3-nano-30b-a3b` — free input/output.
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` — free input/output.
- `poolside/laguna-xs.2` — free input/output.
- `poolside/laguna-m.1` — free input/output.
- `google/gemma-4-31b-it` — free input/output.
- `mistral/leanstral-1-5` — free input/output.
- `nvidia/nemotron-3.5-content-safety` — free input/output.

**Limits:**

- New organizations: 200 requests/day + 20 requests/minute, shared across all free models combined. Paying organizations: 1,000/day + 60/minute. Rate-limit errors until the window resets; paid models unaffected.

**Notes:**

- Account required: yes. API key required: yes. Payment/billing info required: no for free models. Phone verification: unknown.
- Requesty imposes no separate gateway rate limit; upstream provider 429s are handled via routing/fallback policies.

**Sources**

- https://docs.requesty.ai/features/free-models
- https://docs.requesty.ai/features/api-limits
- https://docs.requesty.ai/changelog
- https://www.requesty.ai/pricing
- https://www.requesty.ai/models/free
