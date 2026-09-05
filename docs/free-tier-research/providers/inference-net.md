---
name: Inference.net
url: "https://inference.net"
setup_instructions: |
  1. Register at https://inference.net/register/ for the $0 pay-as-you-go plan.
  2. Create an API key.
  3. Call the API at https://api.inference.net/v1 with the key.
api_key_url: "https://inference.net"
limits:
  requests:
    minute: 30
---

Inference.net's $0 pay-as-you-go plan ("start free … ship your first project") includes 1M Gateway requests under monthly-credit terms, at a 30 req/min rate limit.

**Free Tier:**

- $0 pay-as-you-go plan includes 1M Gateway requests; "every plan includes monthly credits you can spend on fine-tuning, evals, gateway routing, and observability."
- 1 seat, 1M/mo tracing spans, 14-day data retention on the free plan.

**Free Models:**

- Gateway model catalog at https://inference.net/models/ — resolve free-routed IDs live (roster not hardcoded here).

**Limits:**

- 30 requests/min on the free plan (Growth $250/mo raises to 250/min + 50M gateway requests/mo).

**Notes:**

- Account required; API key required; payment requirement for the $0 plan: unknown.
- Endpoint `https://api.inference.net/v1` is fixture-reported; confirm against https://docs.inference.net before use.
- "Gateway requests" wording is the provider's; verify it maps to LLM inference calls for your use case.

**Sources**

- https://inference.net/pricing (free-plan terms verified 2026-09-05)
- https://docs.inference.net
