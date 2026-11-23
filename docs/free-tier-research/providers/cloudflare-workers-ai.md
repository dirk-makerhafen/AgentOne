---
name: Cloudflare Workers AI
url: https://www.cloudflare.com
api_base: https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1
setup_instructions: '1. Sign up for a Cloudflare account at https://dash.cloudflare.com/sign-up/workers-and-pages.

  2. In the dashboard open the Workers AI page and select "Use REST API".

  3. Create a Workers AI API token (template pre-fills Workers AI Read and Edit permissions)
  and copy it together with your Account ID.

  4. POST to https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}
  with header "Authorization: Bearer {token}".

  '
api_key_url: https://dash.cloudflare.com/?to=/:account/ai/workers-ai
---

Workers AI includes a permanent daily free allocation of 10,000 Neurons (GPU-compute units) on both Workers Free and Workers Paid plans, shared across all models.

**Sources**

- https://developers.cloudflare.com/workers-ai/platform/pricing/ (updated 2026-08-28)
- https://developers.cloudflare.com/workers-ai/platform/limits/ (updated 2026-08-07)
- https://developers.cloudflare.com/workers-ai/get-started/rest-api/
