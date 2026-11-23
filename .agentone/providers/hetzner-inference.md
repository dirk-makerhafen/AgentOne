---
name: Hetzner Inference API
url: https://experiments.hetzner.com
api_base: https://inference.hetzner.com/api/v1
setup_instructions: '1. Sign in with your Hetzner customer account at https://experiments.hetzner.com.

  2. In the left navigation under APPS, select "Inference".

  3. Click "Create API Token" (top-right) and copy the token.

  4. Point any OpenAI-compatible client at base URL https://inference.hetzner.com/api/v1
  using the token as the API key.

  5. Resolve the current roster live via GET /v1/models (the response is definitive;
  selection changes during the experiment).

  '
api_key_url: https://experiments.hetzner.com/inference
---

OpenAI-compatible inference API for open-weight LLMs, hosted by Hetzner on its own hardware under its Experiments platform.

**Sources**

- https://docs.hetzner.com/general/company-and-policy/experiments/inference/ (models, limits, free terms, endpoints, verified 2026-09-05)
- https://docs.hetzner.com/general/company-and-policy/experiments/experiments-platform/ (customer-account access, no-cost terms, verified 2026-09-05)
- https://www.hetzner.com/blog/inference-experiment/ (experiment context)
- https://community.hetzner.com/tutorials/opencode-with-hetzner-inference-api-systemd-sandbox/ (setup flow)
