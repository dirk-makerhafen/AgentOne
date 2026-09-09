---
name: IBM watsonx.ai
url: "https://www.ibm.com/products/watsonx-ai"
setup_instructions: |
  1. Create an IBM Cloud account and complete identity verification.
  2. Provision a watsonx.ai Runtime service instance on the Lite (free) plan.
  3. Create service credentials / an API key for the instance.
  4. Call foundation-model inference per the watsonx.ai documentation (endpoint is region-specific; verify live in your datacenter).
api_key_url: "https://www.ibm.com/products/watsonx-ai/pricing"
limits:
  requests:
    second: 2
  tokens:
    month: 300000
---

Enterprise AI platform whose Lite plan is an always-free monthly tier for evaluation (re-verified 2026-09-05 against the official plans table dated 2026-06-16 and the pricing page).

**Free Tier:**

- Lite plan: permanent free tier with monthly-reset quotas (not a one-time trial).

**Free Models:**

- Foundation-model catalog varies by datacenter (includes IBM Granite, Meta Llama, Mistral and other third-party models); no fixed free-model ID list is published on the plan page — verify live in your region.
- No `models/` card links: the pay-go catalog lists models such as `gpt-oss-120b`, but per-model inclusion in the Lite free allowance is unpublished, so no free row can be asserted for any catalog card.

**Limits:**

- 300,000 foundation-model inference tokens per month (1000 tokens = 1 RU, input + output combined) plus 20 CUH per month runtime usage plus 100 document pages per month; 2 inference requests per second per plan ID. No tuning, no custom foundation models, deployments idle after 1 day.

**Notes:**

- Account required: yes (IBM Cloud + identity verification). API key required: yes. Payment/billing info required: unknown per official plan docs (secondary sources report card-based identity verification). Phone verification: unknown. Whether Lite is limited to one instance per account is unverified in current official docs.
- The prior file revision claimed the limits schema covers only minute/day windows — incorrect: `second` and `month` are supported periods, so the documented 2 req/s and 300K tokens/month are now in frontmatter.

**Sources**

- https://www.ibm.com/docs/en/watsonx/saas?topic=runtime-watsonxai-plans
- https://www.ibm.com/products/watsonx-ai/pricing
