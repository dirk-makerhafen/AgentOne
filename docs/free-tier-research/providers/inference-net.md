---
name: Inference.net
url: "https://inference.net"
setup_instructions: |
  1. Create an account at https://inference.net/register/ (starts on the $0 pay-as-you-go plan).
  2. Create a project API key in the dashboard (https://inference.net/dashboard) under API Keys.
  3. Point any OpenAI-compatible client at https://api.inference.net/v1 with the project key as Bearer token.
  4. Serverless model calls are billed per token to your credit balance; proxy (Gateway) calls need your own downstream provider key in x-inference-provider-api-key.
api_key_url: "https://inference.net/dashboard"
limits:
  requests:
    minute: 30
---

Inference.net's $0 pay-as-you-go plan ("start free … ship your first project") includes 1M Gateway requests with a 30 req/min rate limit — but serverless LLM calls are billed per token and the $0 plan documents no free inference-credit grant, so genuinely free LLM API inference is NOT verified (see Notes).

**Free Tier:**

- $0 pay-as-you-go plan includes 1M Gateway requests; "every plan includes monthly credits you can spend on fine-tuning, evals, gateway routing, and observability."
- 1 seat, 1M/mo tracing spans, 14-day data retention on the free plan.
- Growth ($250/mo) adds a $50 one-time opening credit, 50M/mo Gateway requests, 250 req/min.

**Free Models:**

- None verified free: the model catalog (59 models) lists per-token prices for every entry with no $0 rows. Gateway proxy routing works with your own provider keys (OpenAI, Anthropic, etc. — billed by those providers). Resolve IDs live at https://inference.net/models/ (roster not hardcoded here).

**Limits:**

- 30 requests/min on the free plan (documented; in frontmatter). 1M included Gateway requests stated without an explicit period, so no monthly figure is recorded in frontmatter.
- Growth $250/mo raises to 250 req/min + 50M/mo Gateway requests.

**Notes:**

- Account required; API key required; no payment/card requirement documented for the $0 plan (unknown — not asserted either way).
- Why free inference is unverified: the API quickstart defines serverless calls as "billed per token to your credit balance," and only the Growth plan documents a credit grant ($50 one-time). The "1M included Gateway requests" wording is the provider's — it is not documented to cover serverless inference tokens, so it must not be read as 1M free LLM calls.
- Endpoint `https://api.inference.net/v1` confirmed by the official Gateway overview and quickstart (the discovery fixture's `https://inference.net/v1` without the `api.` subdomain is stale — use the docs value).
- Kept as a lead, not a verified free-LLM provider: re-check the pricing page for any future free-credit grant or $0 serverless tier before listing any model as free via Inference.net.

**Sources**

- https://inference.net/pricing (free-plan terms, 30 req/min, $50 Growth credit, verified 2026-09-05)
- https://docs.inference.net/api/api-quickstart (serverless billed per token; endpoint; verified 2026-09-05)
- https://docs.inference.net/integrations/gateway/overview (endpoint https://api.inference.net/v1; proxy needs own provider key; verified 2026-09-05)
- https://inference.net/models/ (59-model catalog, all per-token priced, no $0 rows; verified 2026-09-05)
