---
name: SiliconFlow
url: "https://www.siliconflow.cn/"
setup_instructions: |
  1. Log in at https://cloud.siliconflow.cn/ via SMS or email.
  2. Complete real-name verification under User Center → Real-name Authentication (individual: Mainland ID, Home Return Permit, residence permit, or foreign permanent-resident permit plus Alipay face scan; corporate: legal-person face scan or bank-transfer verification; users without these documents must request manual review via the contact form).
  3. Create an API key at Account → API Keys (https://cloud.siliconflow.cn/account/ak).
  4. Call https://api.siliconflow.cn/v1 with any OpenAI-compatible client, using a free-model ID from https://cloud.siliconflow.cn/models.
api_key_url: "https://cloud.siliconflow.cn/account/ak"
limits:
---

SiliconFlow (Beijing SiliconFlow Technology) is a CN-hosted inference platform with OpenAI- and Anthropic-compatible APIs. Verified users get permanent $0-billed free models alongside paid pay-as-you-go models.

**Free Tier:**

- Permanent free models billed at 0 in the account bill after identity verification — not trial credits.
- Free-model rate limits are fixed values; paid-model limits scale with monthly-spend usage levels L0–L5.

**Free Models:**

- `Qwen/Qwen3-8B` — 128K context (representative, verify live; exact free-model roster is login-gated at cloud.siliconflow.cn/models and rotates).

**Limits:**

- Official docs give only ranges, not per-free-model figures: chat models RPM 1000–10000, TPM 50000–5000000; embedding RPM 2000–10000, TPM 500000–10000000; reranker RPM 2000, TPM 500000. Exact per-free-model RPM/TPM unknown — visible only after login.
- Secondary sources disagree (1,000 RPM / 50,000 TPM vs 30 RPM / 60K TPM) — both unverified, do not use.
- Limits are enforced per account (not per key) and per model; over-limit calls return HTTP 429.

**Notes:**

- Account and API key required; no payment/billing info required for free models.
- Real-name identity verification required (CN ID documents + Alipay face scan, or manual review) — overseas users without qualifying documents may be unable to verify.
- CN-hosted; expect high latency outside Asia-Pacific.
- No credit card required.

**Sources**

- https://docs.siliconflow.cn/docs/userguide/quickstart
- https://docs.siliconflow.cn/docs/userguide/faqs/rate-limit-and-upgradation
- https://docs.siliconflow.cn/docs/userguide/faqs/authentication
- https://freellms.org/providers/siliconflow/
- https://github.com/nejib1/Free-LLM
