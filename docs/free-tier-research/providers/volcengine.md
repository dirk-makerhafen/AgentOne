---
name: Volcengine ModelArk
url: "https://www.volcengine.com/product/ark"
setup_instructions: |
  1. Register a Volcengine account at https://console.volcengine.com/auth/signup (mobile number + verification required).
  2. Complete real-name verification (personal or enterprise) — required to keep using services after the free quota is exhausted.
  3. In the ModelArk console, open 开通管理 and activate the desired model inference service; optionally enable 安心体验模式 (safe-experience mode) so calls consume only the free quota and pause instead of incurring charges.
  4. Create an API key in the Ark console under API Key管理 (https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey).
  5. Call https://ark.cn-beijing.volces.com/api/v3 with any OpenAI-compatible client, using the model ID shown in the console.
api_key_url: "https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey"
limits:
---

ONE-TIME trial grant, not a permanent tier: new accounts receive a one-time free inference quota of 500,000 tokens per model (each model tracked separately, shared under the main account); after exhaustion, calls fail until the model service is activated for pay-as-you-go.

**Free Tier:**

- One-time grant: 500,000 tokens per text/embedding model for new users, granted on registration. Free quota offsets only per-token online-inference fees — not plugins, knowledge bases, batch inference, or context-cache storage fees.
- 安心体验模式 (safe-experience mode): new accounts that have never activated a model service can enable this so API calls consume only the free quota and the service auto-pauses near exhaustion (HTTP 429 SetLimitExceeded) instead of billing. Closing it is irreversible.
- Settlement priority: free online-inference resource pack is deducted before collaboration-reward packs.
- The old "500 resource-points/day" description from third-party lists is outdated; current official docs state per-model token grants, not daily points.

**Free Models:**

- `Doubao-Seed-2.1-pro` — 500,000 tokens (representative API IDs are dated snapshots, e.g. `doubao-seed-2-1-pro-260628` — verify live).
- `Doubao-Seed-2.1-turbo` — 500,000 tokens.
- `Doubao-Seed-Evolving` — 500,000 tokens.
- `Doubao-Seed-Character` — 500,000 tokens.
- `Doubao-embedding-vision` — 500,000 tokens.
- Base and fine-tuned variants of a model share that model's quota. Whether hosted third-party models (DeepSeek, Qwen, GLM, Kimi) carry a free quota is unknown — the product-page quota table lists Doubao models only. Context windows unknown.

**Limits:**

- Grant size (official product page, quoted exactly): 500,000 tokens per listed model. (Not expressed as minute/day rates, so no frontmatter rate figures.)
- Grant validity period unknown — official docs state no expiry in the extracted text; secondary sources conflict (1 year vs 30 days), both unverified.
- Per-minute/per-day RPM/TPM figures unknown. Image-generation (50–200 images), speech (5,000 chars / 20 hours), and web-search plugin (20,000 calls/month) quotas are separate product lines, not LLM chat API.

**Notes:**

- Account required; API key required (`Authorization: Bearer <API_KEY>`).
- Payment/billing info: no payment stated as required to receive or use the free quota; continued use after exhaustion requires real-name verification plus manual service activation, and pay-as-you-go billing applies only after safe-experience mode is closed.
- Real-name verification (personal or enterprise) effectively required for ongoing API use; registration requires a mobile number — exact requirements for overseas users without a mainland phone number or CN ID documents are unknown, and this is the main access barrier.
- Base URL `https://ark.cn-beijing.volces.com/api/v3`, OpenAI-SDK compatible (Coding Plan subscription endpoints under `/api/coding` are separate paid products, not the free quota).
- Paid Coding Plan / Agent Plan subscriptions are distinct offerings and are not free tiers.

**Sources**

- https://www.volcengine.com/docs/82379/1399514
- https://www.volcengine.com/docs/82379/1465347
- https://www.volcengine.com/docs/82379/1330626
- https://www.volcengine.com/docs/82379/1361424
- https://www.volcengine.com/docs/82379/1159200
- https://www.volcengine.com/product/ark
- https://huasheng.ai/insights/volcengine-ark-api-guide/
