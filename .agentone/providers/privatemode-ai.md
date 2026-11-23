---
name: PrivateMode
url: https://www.privatemode.ai
api_base: http://localhost:8080/v1
is_local: true
setup_instructions: '1. Sign in at https://portal.privatemode.ai (create an account;
  new organizations get a one-time 5M-token Initial Token Quota).

  2. Create or select an organization (rate limits, usage, and billing are managed
  at the organization level).

  3. Go to API keys in the portal and create a key (export as PRIVATEMODE_API_KEY).

  4. Call the API either via the Privatemode SDK (`npm i privatemode-ai`) or via the
  local Privatemode proxy (`docker run -p 8080:8080 ghcr.io/edgelesssys/privatemode/privatemode-proxy:latest
  --apiKey <key>`), which exposes an OpenAI-compatible endpoint at http://localhost:8080/v1.
  There is no direct public base URL — traffic goes through the SDK or the local proxy.

  '
api_key_url: https://portal.privatemode.ai
---

PrivateMode (Edgeless Systems, confidential-AI proxy) has a documented Free subscription tier: 1M prompt + 1M completion tokens/month at 20 req/min, plus a one-time 5M-token Initial Token Quota for new organizations (verified 2026-09-05).

**Sources**

- https://docs.privatemode.ai/rate-limits/ (free tier, initial quota, multipliers verified 2026-09-05)
- https://docs.privatemode.ai/pricing/
- https://www.privatemode.ai/pricing (no-credit-card FAQ verified 2026-09-05)
- https://docs.privatemode.ai/getting-started/api/ (SDK + proxy setup verified 2026-09-05)
- https://docs.privatemode.ai/portal/api-keys/
