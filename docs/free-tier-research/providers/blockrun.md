---
name: BlockRun
url: "https://blockrun.ai"
api_base: "https://blockrun.ai/api/v1"
setup_instructions: |
  1. No account, signup, email, phone, identity document, wallet, or API key is needed.
  2. Point an OpenAI-compatible client at https://blockrun.ai/api/v1 and call POST /chat/completions; no Authorization header is required.
  3. Discover the current free routes with GET https://blockrun.ai/api/v1/models (filter `billing_mode: free`).
limits:
  requests:
    minute: 30
    hour: 300
---

BlockRun has a genuinely anonymous free LLM API: the official free page says "No key. No wallet.", "No key, no signup", and no identity information is collected. Verified 2026-11-20.

**Free Tier:**

- No account, key, wallet, or payment method. Keyless anonymous access on the documented free endpoint.
- 30 requests/minute and 300 requests/hour per IP for free chat models. `429` uses error code `FREE_TIER_RATE_LIMITED`.
- No published token quota; do not infer one.

**Free Models:**

Live `GET https://blockrun.ai/api/v1/models` showed 9 `billing_mode: free` / zero-priced routes on 2026-11-20:

- `nvidia/nemotron-3-super-120b` (available)
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`
- `nvidia/nemotron-3.5-lightning`
- `nvidia/nemotron-3-ultra-550b` (available)
- `cohere/north-mini-code`
- `poolside/laguna-xs-2.1` (available)
- `nvidia/muse-glimmer-30b`
- `nvidia/nemotron-3.5-bolt` (available)
- `nvidia/minimax-m3.1-flash` (available)

Catalog lead `nvidia/llama-3.2-11b-vision` is no longer in the live free list. Per-model context windows, tool support and vision support are not verified; the free page mentions vision for `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`, but that route was unavailable at verification.

**Limits:**

- Frontmatter uses the documented per-IP free-tier request caps.

**Notes:**

- Free capacity is borrowed: a busy named model can be answered by a different free model. The response `model` field names the actual answerer — check it when model identity matters.
- The free route is at `/api/v1/chat/completions` and `/api/v1/models`; it is a distinct surface from any paid BlockRun products.

**Sources**

- https://blockrun.ai/free
- https://blockrun.ai/docs/rate-limits
- https://blockrun.ai/api/v1/models
- docs/free-tier-research/raw/freellmapi-catalog/platforms/blockrun.json (discovery lead, verified 2026-11-20)
