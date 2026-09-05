---
name: Alibaba Cloud Model Studio
url: "https://modelstudio.alibabacloud.com/"
setup_instructions: |
  1. Register an Alibaba Cloud account at https://www.alibabacloud.com/.
  2. Open the Model Studio console for the Singapore region (https://modelstudio.console.alibabacloud.com/ap-southeast-1) and accept the service agreement (quota lands within ~2 hours).
  3. Go to API Keys and create an API key (note the API Host/base_url shown; key and endpoint must be the same region).
  4. Enable "Free Quota Only" to stop service instead of switching to pay-as-you-go when the quota runs out.
  5. Call via any OpenAI-compatible client using that base_url and a quota-eligible model name.
api_key_url: "https://modelstudio.console.alibabacloud.com/ap-southeast-1"
limits:
---

ONE-TIME trial grant, not a permanent tier: first-time Model Studio activation automatically grants a per-model free token quota valid 90 days; after exhaustion or expiry, calls stop (new users) or switch to pay-as-you-go.

**Free Tier:**

- **Free Tier:** One-time grant: typically 1,000,000 tokens per model (input + output drawn from one combined total; per-model quotas, non-transferable), valid 90 days from activation/model-release/approval (whichever is later). Real-time inference only — excludes batch, fine-tuning, deployment, custom models, PAI-DSW, OSS fees.
- Singapore-region + International-scope models only (intl site); Beijing/China-Mainland scope on the Chinese site. Re-registering grants no additional quota. Account and RAM users share one quota.

**Free Models:**

- No fixed official list — any model showing a blue quota bar in the console qualifies (representative, verify live). Official examples: `qwen-max`, `qwen-plus`, `qwen3.6-plus`, `qwen3.7-max` (dated snapshot aliases count as separate models with their own quota). The grant applies generally across eligible models, one quota per model.

**Limits:**

- Grant size/duration (official free-quota page, quoted exactly): 1,000,000 tokens per model typical; 90-day validity. (Not expressed as minute/day rates, so no frontmatter rate figures.)
- Per-request QPS/QPM rate limits apply per model — exact figures unknown (official rate-limit page not extracted; never guess).
- Separate OAuth path: 2,000 calls/day free quota (official FAQ).

**Notes:**

- Account required; API key required (new keys start `sk-ws-`; legacy `sk-` still valid; region-specific — cross-region key use returns HTTP 401).
- Payment/billing info: no credit card stated as required for the free quota; continuing past quota requires completing account information (links to a mobile/security page) — phone/mobile verification effectively required for PAYG, exact requirements unknown.
- Base URLs are region-specific, e.g. Singapore `https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`, Beijing `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`, Virginia `https://dashscope-us.aliyuncs.com/compatible-mode/v1` (legacy `dashscope(-intl).aliyuncs.com/compatible-mode/v1` also functional). Anthropic-compatible endpoints also exist.
- Data-training/region-compliance terms: unknown — verify for regulated workloads.

**Sources**

- https://www.alibabacloud.com/help/en/model-studio/new-free-quota
- https://help.aliyun.com/en/model-studio/new-free-quota
- https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope
- https://www.alibabacloud.com/help/en/model-studio/get-api-key
- https://www.alibabacloud.com/help/en/model-studio/base-url
- https://inferencehub.org/blog/alibaba-cloud-qwen-api-pricing-2026/
- https://github.com/nejib1/Free-LLM
