---
name: InferX
url: https://www.inferx.net
api_base: https://model.inferx.net/v1
setup_instructions: '1. Sign in at https://model.inferx.net/login and open an endpoint.

  2. Copy the API Base URL, Model Name, and API Key from the Console Client Setup
  panel (production URLs can be tenant/endpoint-specific — use the exact Console values).

  3. Install the OpenAI client (`pip install openai`) and point it at the base URL
  (default `https://model.inferx.net/v1`) with the key as Bearer token; pass the Model
  Name as `model`.

  4. Re-verify the endpoint-pricing page before use — free models are rotating promotions.

  '
api_key_url: https://model.inferx.net/login
---

InferX (InferX AI, San Francisco) is a serverless inference provider with an "InferX Free" $0/mo tier: free promotional models on enterprise GPUs behind an OpenAI-compatible API with zero data retention.

**Sources**

- https://inferx.net/pricing/endpoints (endpoint pricing with $0 rows for the 5 free models, verified 2026-09-05)
- https://www.inferx.net/pricing (InferX Free $0/mo terms, verified 2026-09-05)
- https://www.inferx.net/models (free flags + contexts for Qwen3.6 pair, verified 2026-09-05)
- https://inferx.net/docs/quickstart
- https://inferx.net/docs/api-reference (rate-limit tiers withheld, verified 2026-09-05)
