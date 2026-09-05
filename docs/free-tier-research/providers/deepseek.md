---
name: DeepSeek Platform
url: "https://platform.deepseek.com/"
setup_instructions: |
  1. Sign up at https://platform.deepseek.com/.
  2. Apply for an API key at https://platform.deepseek.com/api_keys and store it server-side.
  3. Top up a balance if needed; if your account carries a grant balance it is consumed first (per the official pricing page, verified 2026-09-05).
  4. Call https://api.deepseek.com/chat/completions (OpenAI-compatible) or https://api.deepseek.com/anthropic (Anthropic-compatible) with any compatible client.
api_key_url: "https://platform.deepseek.com/api_keys"
limits:
---

ONE-TIME trial grant, not a permanent tier: DeepSeek's API is pay-per-token with no free-forever tier. The official pricing page confirms a "granted balance" exists (deducted before any topped-up balance), but no grant amount, expiry, or eligibility is documented on any official page — the commonly cited figures (5M tokens, 30-day expiry, no card) are secondary-reported and must be confirmed in the platform console. (Consumer chat at chat.deepseek.com is separately free with fair-use throttling.)

**Free Tier:**

- **Free Tier:** One-time grant only (secondary-reported: 5M tokens, 30-day expiry, no credit card — explicitly unverified against official docs as of 2026-09-05; confirm the live offer in the platform console before relying on it). Treat as testing capacity, not production quota.

**Free Models:**

- No officially designated free models; any grant balance applies generally to API use. Current API model IDs (official docs, verified 2026-09-05): [`deepseek-v4-flash`](../models/deepseek-v4-flash.md) (DeepSeek-V4-Flash-0731), [`deepseek-v4-pro`](../models/deepseek-v4-pro.md) (DeepSeek-V4-Pro-0813), `deepseek-v4-flash-vision-exp` (experimental, image input billed as input tokens by dimension).
- All three serve 1M context with up to 384K max output and support JSON output, tool calls, Responses API, Anthropic API, and chat-prefix completion (official pricing page, verified 2026-09-05).

**Limits:**

- Documented free-tier RPM/RPD/TPM figures: none (no free-tier rate card exists; never guess).
- Account-level concurrency limits (official rate-limit page, verified 2026-09-05; paid accounts, not a free tier): `deepseek-v4-flash` 2500, `deepseek-v4-pro` 500, `deepseek-v4-flash-vision-exp` 2500; 429 on exceed.
- Paid reference (official pricing page, verified 2026-09-05; peak/off-peak card): V4 Flash cache-miss $0.44/$0.22 per 1M input, cache-hit $0.014/$0.007, output $1.32/$0.66; V4 Pro cache-miss $1.32/$0.66, cache-hit $0.044/$0.022, output $3.96/$1.98. Peak is 01:00–04:00 and 06:00–10:00 UTC, Monday–Friday; off-peak is half the peak rate.

**Notes:**

- Account required; API key required even when using grant balance.
- Payment/billing info: secondary sources say no credit card required for the grant — unverified officially, card requirement unknown. Phone verification: unknown.
- Endpoint is OpenAI-compatible (`https://api.deepseek.com`) and Anthropic-compatible (`https://api.deepseek.com/anthropic`) (official first-call page, verified 2026-09-05).
- Infrastructure is mainland-China-operated under Chinese data-handling law (third-party note) — compliance-sensitive workloads should use third-party hosts or self-host.
- Never expose API keys in browser code or public repos.

**Sources**

- https://api-docs.deepseek.com/quick_start/pricing (models, 1M context/384K output, peak/off-peak rates, granted-balance deduction — verified 2026-09-05)
- https://api-docs.deepseek.com/ (first API call: model IDs, base URLs, api_keys link — verified 2026-09-05)
- https://api-docs.deepseek.com/quick_start/rate_limit (concurrency limits — verified 2026-09-05)
- https://platform.deepseek.com/
- https://felloai.com/deepseek-pricing/ (2026-08-22; secondary — grant figures and rate citations only)
- https://github.com/nejib1/Free-LLM
