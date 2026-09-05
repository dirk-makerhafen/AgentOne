---
name: Moark
url: "https://moark.ai"
setup_instructions: |
  1. Register at https://moark.ai and obtain the Free Trial Access Token.
  2. Call the API at https://moark.com/v1 with the token.
  3. Stay within 100 free calls/day; buy a resource pack for more.
api_key_url: "https://moark.ai"
limits:
  requests:
    day: 100
---

Moark documents a "Free Trial Access Token" with 100 free calls/day on an ongoing daily cap; a paid resource pack applies beyond that.

**Free Tier:**

- 100 free calls/day via the Free Trial Access Token (daily cap, documented as ongoing in the official FAQ).
- Paid resource pack for usage beyond the daily cap.

**Free Models:**

- Trial-token model set (docs cite free models such as Qwen3-8B for prototyping) — resolve live in the docs; fixture rows (`GLM-4.7`, `MiniMax-M2.1`) are paid-listed, not the free set.

**Limits:**

- 100 requests/day (free token). Per-minute numerics: unknown.

**Notes:**

- Verification is thin (single FAQ + text-generation docs); treat as fragile and re-confirm before use.
- Endpoint `https://moark.com/v1` is fixture-reported; confirm against the official docs before use.

**Sources**

- https://moark.ai/docs/appendix/qa
- https://moark.ai/docs/products/apis/texts/text-generation
