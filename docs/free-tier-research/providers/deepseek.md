---
name: DeepSeek Platform
url: "https://platform.deepseek.com/"
setup_instructions: |
  1. Sign up at https://platform.deepseek.com/.
  2. Create or select a project for the integration.
  3. Generate an API key (platform.deepseek.com/api_keys) and store it server-side.
  4. Check the console for grant balance/billing state before building (grant presence is not guaranteed).
  5. Call https://api.deepseek.com/chat/completions with any OpenAI-compatible client.
api_key_url: "https://platform.deepseek.com/"
limits:
---

ONE-TIME trial grant, not a permanent tier: DeepSeek's API is pay-per-token with no free-forever tier; new accounts are reported to receive a one-time token grant, after which billing switches to standard per-token rates. (Consumer chat at chat.deepseek.com is separately free with fair-use throttling.)

**Free Tier:**

- **Free Tier:** One-time grant (secondary-reported: 5M tokens, 30-day expiry — explicitly unverified against official docs; confirm the live offer in the platform console before relying on it). Treat as testing capacity, not production quota.

**Free Models:**

- No officially designated free models; the grant applies generally to API use. Current API model IDs (official docs): [`deepseek-v4-flash`](../models/deepseek-v4-flash.md) (→ DeepSeek-V4-Flash-0731), [`deepseek-v4-pro`](../models/deepseek-v4-pro.md) (→ DeepSeek-V4-Pro-0813), `deepseek-v4-flash-vision-exp` (experimental, image input).

**Limits:**

- Documented free-tier RPM/RPD/TPM figures: unknown (official rate-limit page exists at /quick_start/rate_limit but figures were not extracted; never guess).
- Paid reference points are third-party citations of the official pricing page (2026; re-check live): V4 Flash ~$0.14/M input / $0.28/M output; V4 Pro ~$0.435/M input / $0.87/M output.

**Notes:**

- Account required; API key required even when using grant balance.
- Payment/billing info: secondary sources say no credit card required for the grant — unverified officially, card requirement unknown. Phone verification: unknown.
- Endpoint is OpenAI-compatible (`https://api.deepseek.com`) and Anthropic-compatible (`https://api.deepseek.com/anthropic`).
- Infrastructure is mainland-China-operated under Chinese data-handling law (third-party note) — compliance-sensitive workloads should use third-party hosts or self-host.
- Never expose API keys in browser code or public repos.

**Sources**

- https://api-docs.deepseek.com/
- https://platform.deepseek.com/
- https://api-docs.deepseek.com/quick_start/pricing (JS-gated; figures via dated citations)
- https://felloai.com/deepseek-pricing/ (2026-08-31)
- https://www.layer3labs.io/guides/deepseek-pricing (2026-07-21)
- https://github.com/nejib1/Free-LLM
