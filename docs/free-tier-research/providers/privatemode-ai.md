---
name: PrivateMode
url: "https://www.privatemode.ai"
setup_instructions: |
  1. Sign in at https://portal.privatemode.ai (create an account; new organizations get a one-time 5M-token Initial Token Quota).
  2. Create or select an organization (rate limits, usage, and billing are managed at the organization level).
  3. Go to API keys in the portal and create a key (export as PRIVATEMODE_API_KEY).
  4. Call the API either via the Privatemode SDK (`npm i privatemode-ai`) or via the local Privatemode proxy (`docker run -p 8080:8080 ghcr.io/edgelesssys/privatemode/privatemode-proxy:latest --apiKey <key>`), which exposes an OpenAI-compatible endpoint at http://localhost:8080/v1. There is no direct public base URL — traffic goes through the SDK or the local proxy.
api_key_url: "https://portal.privatemode.ai"
limits:
  requests:
    minute: 20
  tokens:
    input:
      minute: 200000
      month: 1000000
    output:
      minute: 20000
      month: 1000000
---

PrivateMode (Edgeless Systems, confidential-AI proxy) has a documented Free subscription tier: 1M prompt + 1M completion tokens/month at 20 req/min, plus a one-time 5M-token Initial Token Quota for new organizations (verified 2026-09-05).

**Free Tier:**

- Standing monthly free quota (not a trial): 1M prompt + 1M completion tokens/month; 200K prompt/min, 20K completion/min, 500K cached-prompt/min, 20 req/min. Audio: 100 minutes/min and 100 minutes/month.
- New organizations also get a one-time 5M-token Initial Token Quota; while positive, non-cached usage is deducted from it and standard monthly limits don't apply (spending budgets still enforced). Audio STT burns quota at ~2,800 tokens/min. Cached tokens never count toward quota.
- No credit card required for the Free tier (official pricing FAQ, verified 2026-09-05). Standard tier is pay-as-you-go with no monthly cap.

**Free Models (multiplier-adjusted quota; baseline Kimi K2.6 = 1.0):**

- `Kimi K2.6` — chat, multiplier 1.0 (full 1M/month quota). SDK quickstart uses the alias `kimi-latest`.
- [`GLM-5.3`](../models/glm-5.3.md) — chat, multiplier 1.0 (rate-limits page; note the pricing table still lists `GLM-5.2`, so confirm the live model ID before use).
- `DeepSeek OCR 2` — vision OCR, multiplier 1.0.
- [`gpt-oss-120b`](../models/gpt-oss-120b.md) — reasoning, multiplier 2.0 (effective 500K/month).
- `Qwen3-Embedding 4B` — embeddings, multiplier 0.5 (effective 2M/month).
- Speech-to-text (`Voxtral Mini 3B`, `Whisper large-v3`) is priced per audio minute and burns the initial quota; monthly audio cap is 100 minutes.

**Limits:**

- See frontmatter (token figures are multiplier-adjusted per model; cached tokens don't count toward quota).

**Notes:**

- Account/org required; API key required; no payment method required for Free-tier use.
- There is no direct public API base URL: use the SDK or the local proxy (`http://localhost:8080/v1`); the fixture-reported `http://localhost:8080/v1` is the proxy endpoint, not a hosted endpoint.
- All prices plus VAT where applicable; usage inspectable on the portal usage page.

**Sources**

- https://docs.privatemode.ai/rate-limits/ (free tier, initial quota, multipliers verified 2026-09-05)
- https://docs.privatemode.ai/pricing/
- https://www.privatemode.ai/pricing (no-credit-card FAQ verified 2026-09-05)
- https://docs.privatemode.ai/getting-started/api/ (SDK + proxy setup verified 2026-09-05)
- https://docs.privatemode.ai/portal/api-keys/
