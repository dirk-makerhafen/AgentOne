---
name: Moondream
url: "https://moondream.ai"
api_base: "https://api.moondream.ai/v1"
setup_instructions: |
  1. Create a Moondream Cloud account at https://console.moondream.ai (no card).
  2. Generate an API key in the console.
  3. Point an OpenAI-compatible client at https://api.moondream.ai/v1 and call `moondream3.1-9B-A2B`.
  4. Inline images as base64 data URLs; remote http(s) image URLs return 400.
api_key_url: "https://console.moondream.ai"
limits:
  requests:
    second: 2
---

Moondream Cloud is a hosted vision-language API with a recurring $5 free credit every month, no card required. Verified 2026-11-20.

**Free Tier:**

- $5.00 in free credits added every month to each workspace (no card). Funded accounts (balance >= $10) get a higher rate limit but are not required.
- Base tier: 2 requests/second for both free models; 10 req/s if account balance >= $10.
- `max_completion_tokens` <= 4096 including reasoning.
- A blog post mentions "5,000 daily requests", but the authoritative rate-limits page publishes only the 2 RPS tier; the daily figure is unverified.

**Free Models:**

- `moondream3.1-9B-A2B` — vision-language; base64 data URLs only, multi-image supported; reasoning via `extra_body={"reasoning": true}` returned on `message.reasoning`; streaming supported. No tool/function calling, no stop sequences. Context window not published officially (catalog is null; OpenRouter's 32K is a different provider).
- `moondream3-preview` — same constraints.

**Limits:**

- Frontmatter records the documented 2 RPS base tier. No daily token quota is published.

**Notes:**

- This is a hosted API, not self-hosted weights.
- Privacy-first positioning: "we never train Moondream models on your data."
- Prepaid token validity is 12 months; irrelevant to the recurring free credits.
- Catalog capability flags (vision=true, tools=false) match official docs.

**Sources**

- https://moondream.ai/pricing
- https://docs.moondream.ai/pricing
- https://docs.moondream.ai/openai
- https://docs.moondream.ai/rate-limits
- https://moondream.ai/blog/announcing-moondream-cloud
- docs/free-tier-research/raw/freellmapi-catalog/platforms/moondream.json (discovery lead, verified 2026-11-20)
