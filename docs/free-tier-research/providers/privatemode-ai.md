---
name: PrivateMode
url: "https://www.privatemode.ai"
setup_instructions: |
  1. Create an organization at https://portal.privatemode.ai (new orgs get a one-time 5M-token Initial Token Quota on top of the free tier).
  2. Create an API key (PRIVATEMODE_API_KEY) in the portal.
  3. Call the OpenAI-compatible API via the Privatemode proxy — see the API quickstart for the endpoint.
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

PrivateMode (Edgeless Systems, confidential-AI proxy) has a documented Free subscription tier: 1M prompt + 1M completion tokens/month at 20 req/min, plus a one-time 5M-token Initial Token Quota for new organizations.

**Free Tier:**

- Standing monthly free quota (not a trial): 1M prompt + 1M completion tokens/month; 200K prompt/min, 20K completion/min, 500K cached-prompt/min, 20 req/min.
- New organizations also get a one-time 5M-token Initial Token Quota; while positive, monthly limits don't apply (spending budgets still enforced). Audio STT burns quota at ~2,800 tokens/min.
- Standard tier is pay-as-you-go with no monthly cap.

**Free Models (multiplier-adjusted quota; baseline Kimi K2.6 = 1.0):**

- `Kimi K2.6` — chat, multiplier 1.0 (full 1M/month quota).
- `GLM-5.3` — chat, multiplier 1.0.
- `DeepSeek OCR 2` — vision OCR, multiplier 1.0.
- `gpt-oss-120b` — reasoning, multiplier 2.0 (effective 500K/month).
- `Qwen3-Embedding 4B` — embeddings, multiplier 0.5 (effective 2M/month).

**Limits:**

- See frontmatter (token figures are multiplier-adjusted per model; cached tokens don't count toward quota).

**Notes:**

- Account/org required; API key required; payment requirement for free-tier-only use: unknown.
- All prices plus VAT where applicable; usage inspectable on the portal usage page.

**Sources**

- https://docs.privatemode.ai/rate-limits/ (free tier + initial quota verified 2026-09-05)
- https://docs.privatemode.ai/pricing/
