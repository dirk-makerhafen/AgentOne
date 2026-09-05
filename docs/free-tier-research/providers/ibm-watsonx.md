---
name: IBM watsonx.ai
url: "https://www.ibm.com/products/watsonx-ai"
setup_instructions: |
  1. Create an IBM Cloud account and complete identity verification.
  2. Provision a watsonx.ai Runtime instance on the Lite (free) plan (one Lite instance per account).
  3. Create service credentials / an API key for the instance.
  4. Call foundation-model inference per the watsonx.ai documentation.
api_key_url: "https://www.ibm.com/products/watsonx-ai/pricing"
limits:
---

Enterprise AI platform whose Lite plan is an always-free monthly tier for evaluation.

**Free Tier:**

- Lite plan: permanent free tier with monthly-reset quotas (not a one-time trial).

**Free Models:**

- Foundation-model catalog varies by datacenter (includes IBM Granite, Meta Llama, Mistral and other third-party models); no fixed free-model ID list is published on the plan page — verify live in your region.

**Limits:**

- 300,000 foundation-model inference tokens per month (1000 tokens = 1 RU) plus 20 CUH per month runtime usage plus 100 document pages per month; 2 inference requests per second per plan ID. No tuning, no custom foundation models, deployments idle after 1 day. Per-second/per-month figures are documented here but omitted from frontmatter (schema covers only minute/day windows).

**Notes:**

- Account required: yes (IBM Cloud + identity verification, one Lite instance per account). API key required: yes. Payment/billing info required: unknown per official plan docs (secondary sources report card-based identity verification). Phone verification: unknown.

**Sources**

- https://www.ibm.com/docs/en/watsonx/saas?topic=runtime-watsonxai-plans
- https://www.ibm.com/products/watsonx-ai/pricing
