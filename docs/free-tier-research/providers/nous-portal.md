---
name: Nous Portal
url: https://portal.nousresearch.com/
api_base: https://inference-api.nousresearch.com/v1
setup_instructions: '1. Register an account at https://portal.nousresearch.com/ and
  stay on the Free ($0/mo, $0 monthly credits) plan.

  2. Generate an API key in the portal.

  3. Point any OpenAI-compatible client at base URL https://inference-api.nousresearch.com/v1
  with the key as Bearer token and a Portal-price-FREE model ID.

  '
api_key_url: https://portal.nousresearch.com/
---

Nous Research's official API portal exposes 390 models (live count 2026-09-05, including its Hermes family) through an OpenAI-compatible API at `https://inference-api.nousresearch.com/v1`, with a standing $0 Free plan limited to free models.

**Sources**

- https://portal.nousresearch.com/ (Free plan: free models only, $0 monthly credits)
- https://portal.nousresearch.com/api-docs (rate limits, x402 beta — JS-rendered; corroborated via secondaries below)
- https://portal.nousresearch.com/models (live FREE rows + 390-model count, checked 2026-09-05)
- https://portal.nousresearch.com/manage-subscription (Plus/Super/Ultra credit figures)
- https://hermes-agent.nousresearch.com/docs/integrations/nous-portal (base URL `https://inference-api.nousresearch.com/v1`, backend routing)
- https://dev.to/zackchew/nous-portal-explained-plans-models-tools-and-hermes-cloud-9hh (2026-08-02: Free $0/mo, 50 RPM / 500K TPM)
- https://github.com/nejib1/Free-LLM
