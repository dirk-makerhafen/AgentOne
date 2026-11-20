---
name: Plugsky
url: "https://plugsky.com"
api_base: "https://plugsky.com/v1"
setup_instructions: |
  1. Create a free account at https://plugsky.com (no card; free trials were retired in Nov 2026).
  2. Generate a key (`sk-live-...`) in Dashboard -> API keys.
  3. Point an OpenAI-compatible client at https://plugsky.com/v1 and call `plugsky-micro` or `plugsky-lite`.
api_key_url: "https://plugsky.com"
limits:
  requests:
    minute: 30
    day: 500
  tokens:
    day: 250000
---

Plugsky has a permanent $0 Free plan with two chat models. Account + key required, no payment. Verified 2026-11-20.

**Free Tier:**

- Free plan: 500 requests/day (100 for the first 24h), 250,000 tokens/day (50K new), 30 RPM, 2 concurrent (1 new). Resets 00:00 UTC.
- `X-Plugsky-Quota-Warning` header at 80%; `429` + `Retry-After` at 100%.
- Per-request cap: 32K input / 2K output tokens. This is a request constraint, not a usage-over-time limit, so it is not in frontmatter `limits`.
- Internal docs conflict on API-key count (one table says 2, prose says unlimited); no key count is recorded.

**Free Models:**

- `plugsky-micro` — chat + JSON only. Catalog reports 262,144 context, but the official Free plan caps input at 32K / output 2K; use the official cap.
- `plugsky-lite` — chat + JSON only; same 32K/2K cap.
- Tools/function calling, vision, image generation, RAG and Agents are locked until upgrade. Catalog flags match.

**Limits:**

- Frontmatter uses the documented Free-plan request/token allowances.

**Notes:**

- Backing models may change or fail over; streaming can reveal the upstream.
- "Smart routing"/Fusion and aliases like `gpt-4o` auto-map to Plugsky models.
- An Anthropic-compatible endpoint exists at `https://api.plugsky.com`.

**Sources**

- https://plugsky.com/docs
- https://plugsky.com/articles/how-much-does-an-ai-api-cost-in-2026
- https://plugsky.com/compare/openai-api-vs-plugsky
- docs/free-tier-research/raw/freellmapi-catalog/platforms/plugsky.json (discovery lead, verified 2026-11-20)
