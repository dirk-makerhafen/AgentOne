---
name: Tencent Hunyuan
url: "https://cloud.tencent.com/product/hunyuan"
setup_instructions: |
  1. Register a Tencent Cloud account at https://cloud.tencent.com/ and complete real-name verification (personal or enterprise 实名认证) — required before activation.
  2. Open the Hunyuan console and click 立即使用 (https://console.cloud.tencent.com/hunyuan/settings) — the one-time free resource pack is issued automatically on first activation.
  3. Create an API key at Console > API Key page (https://console.cloud.tencent.com/hunyuan/start). Main account only for create/delete.
  4. Call https://api.hunyuan.cloud.tencent.com/v1 (full chat path /v1/chat/completions) with any OpenAI-compatible client using a quota-eligible model name. New model capabilities are moving to TokenHub (https://console.cloud.tencent.com/tokenhub).
api_key_url: "https://console.cloud.tencent.com/hunyuan/start"
limits:
---

ONE-TIME trial grant, not a permanent tier (re-verified 2026-09-05 against the billing page last updated 2026-06-26): first activation grants a one-time free resource pack of 1,000,000 tokens (shared across the listed text/vision models; embedding has its own 1,000,000-token pack), valid 1 year from activation; after exhaustion or expiry, calls fail unless postpay is manually enabled.

**Free Tier:**

- One-time grant: 1,000,000 tokens shared across Hunyuan-a13b, Hunyuan-role-latest, Hunyuan-translation, Hunyuan-translation-lite, Tencent HY Vision 1.5 Instruct, Hunyuan-turbos-vision, Hunyuan-t1-vision, Hunyuan-turbos-vision-video; plus a separate 1,000,000-token pack for Hunyuan-embedding. Resource packs valid 1 year from service activation; unused balance expires.
- Settlement order: free resource pack > paid resource pack > postpay. Free/paid packs do NOT auto-convert to postpay — without manually enabling postpay, exhausted/expired quota produces billing-error failures, not charges.
- Image generation is a separate product line with its own one-time packs (50 calls per interface), not covered here.

**Free Models:**

- `Hunyuan-a13b` — text generation, shares the 1M-token pack.
- `Hunyuan-role-latest` — role-play/character model, shares the 1M-token pack.
- `Hunyuan-translation` / `Hunyuan-translation-lite` — translation models, share the 1M-token pack.
- `Tencent HY Vision 1.5 Instruct` / `Hunyuan-turbos-vision` / `Hunyuan-t1-vision` / `Hunyuan-turbos-vision-video` — vision/video-understanding models, share the 1M-token pack.
- `Hunyuan-embedding` — embedding model, own 1M-token pack.
- Model IDs above are quoted exactly as listed on the billing page (2026-06-26); doc code examples use lowercase IDs such as `hunyuan-turbos-latest` and `hunyuan-vision` — verify exact live casing in the console. Context windows unknown.
- None of these models has a card in `models/` (no overlap with the catalog cards), so no card links apply.

**Limits:**

- Grant size/duration (official billing page, quoted exactly): 1,000,000 tokens per pack; 1-year validity. (A one-time grant with yearly validity is not a per-period rate, so no frontmatter rate figures.)
- Concurrency (official OpenAI-compat doc): hunyuan chat interface default limit is 5 concurrent sessions, shared by main/sub-accounts. Per-minute/per-day RPM/TPM figures unknown.

**Notes:**

- Account required; API key required (OpenAI-compatible key created in console, or TencentCloud SecretId/SecretKey for the native SDK).
- Payment/billing info: no payment method stated as required for the free pack; postpay must be manually enabled to continue past quota.
- Real-name verification (personal or enterprise) is mandatory before activation — overseas users face a CN-centric verification flow (exact accepted documents for non-mainland users unknown).
- Base URL `https://api.hunyuan.cloud.tencent.com/v1` (chat path `/v1/chat/completions`); OpenAI-compatible and Anthropic-compatible interfaces documented. Native SDK endpoint `hunyuan.tencentcloudapi.com`.
- Model services are migrating to TokenHub; the legacy Hunyuan console adds no new model capabilities and stops new service purchases. Effect of this migration on new free-pack activations is unverified.
- If the account is in arrears or suspended for violations, the free quota cannot be used until service is restored.

**Sources**

- https://cloud.tencent.com/document/product/1729/97731
- https://cloud.tencent.com/document/product/1729/111007
- https://cloud.tencent.com/document/product/1729/111008
- https://cloud.tencent.com/document/product/1729/116755
- https://cloud.tencent.com/document/product/1668/90897
