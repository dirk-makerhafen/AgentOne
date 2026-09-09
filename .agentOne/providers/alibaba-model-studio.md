---
name: Alibaba Cloud Model Studio
url: "https://modelstudio.alibabacloud.com/"
api_base: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
setup_instructions: |
  1. Register an Alibaba Cloud account at https://www.alibabacloud.com/.
  2. Open the Model Studio console for the Singapore region (https://modelstudio.console.alibabacloud.com/ap-southeast-1), select the region, and accept the service agreement (quota lands within ~2 hours).
  3. Go to the API Key page and create an API key (choose workspace and permissions; note the API Host/base_url shown — key and endpoint must be the same region and billing plan, or calls return 401).
  4. Enable "Free Quota Only" (free-quota-use-stop) to stop service instead of switching to pay-as-you-go when the quota runs out.
  5. Call via any OpenAI-compatible client using that base_url and a quota-eligible model name.
api_key_url: "https://modelstudio.console.alibabacloud.com/ap-southeast-1"
limits: {}
---

ONE-TIME trial grant, not a permanent tier: first-time Model Studio activation automatically grants a per-model free token quota valid 90 days; after exhaustion or expiry, calls stop (new users) or switch to pay-as-you-go (verified 2026-09-05).

**Free Tier:**

- One-time grant: typically 1,000,000 tokens per model (input + output drawn from one combined total; per-model quotas, non-transferable), valid 90 days from activation/model-release/approval (whichever is later). Real-time inference only — excludes batch, fine-tuning, deployment, custom models, PAI-DSW, OSS fees.
- Singapore-region + International-scope models only (intl site); Beijing/China-Mainland scope on the Chinese site. Re-registering grants no additional quota. Account and RAM users share one quota.
- No per-period (minute/day) free-quota rates are documented, so the frontmatter `limits` stays empty; the grant is a fixed token quota with an expiry date, not a rate.

**Free Models:**

- No fixed official list — any model showing a blue quota bar / remaining free-quota amount in the console qualifies (verify live). Models explicitly listed with a 1M-token free quota on the official model-pricing page (verified 2026-09-05): `qwen3.7-max` (incl. dated snapshots), `qwen3.6-flash`, `qwen3.5-flash`, `qwen-flash`; the free-quota doc uses `qwen-max` / `qwen-plus` as examples. Dated snapshot aliases count as separate models with their own quota.
- None of these IDs currently has a model card in `models/`, so no card links apply.

**Limits:**

- Grant size/duration (official free-quota page, quoted exactly): 1,000,000 tokens per model typical; 90-day validity.
- Per-model RPM/TPM rate limits apply on top of the quota (429 on excess; 403 when the free quota is exhausted with stop-enabled) — exact per-model figures are account/model-specific and were not extracted; never guess.
- Separate OAuth path: 2,000 calls/day free quota (official FAQ), independent of the API-key token quota.

**Notes:**

- Account required; API key required (new keys start `sk-ws-`; legacy `sk-` still valid; region- and plan-specific — cross-region or plan-mismatched key use returns HTTP 401).
- Payment/billing info: no credit card stated as required for the free quota; continuing past quota requires completing account information (links to a mobile/security page) — phone/mobile verification effectively required for PAYG, exact requirements unknown.
- Base URLs are region- and plan-specific (verified 2026-09-05): Singapore OpenAI-compatible `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`; workspace-dedicated `https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`; trial `https://trial.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`. Token Plan and Coding Plan have their own dedicated domains and keys (interactive coding tools only). Anthropic-compatible endpoints also exist.
- Data-training/region-compliance terms: unknown — verify for regulated workloads.

**Sources**

- https://www.alibabacloud.com/help/en/model-studio/new-free-quota (grant rules, Singapore scope verified 2026-09-05)
- https://www.alibabacloud.com/help/en/model-studio/billing-for-model-studio (per-model 1M quotas verified 2026-09-05)
- https://www.alibabacloud.com/help/en/model-studio/get-api-key (key steps verified 2026-09-05)
- https://www.alibabacloud.com/help/en/model-studio/base-url (endpoints verified 2026-09-05)
- https://www.alibabacloud.com/help/en/model-studio/new-free-quota-validity-adjustment (validity notice, updated 2026-09-04)
- https://help.aliyun.com/zh/model-studio/rate-limit (429 vs 403 semantics)
- https://github.com/nejib1/Free-LLM (discovery only)
