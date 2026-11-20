---
name: CLōD
url: "https://clod.io"
api_base: "https://api.clod.io/v1"
setup_instructions: |
  1. Sign up at https://app.clod.io on the free tier (no card required for the base tier).
  2. Create an API key and send it as `Authorization: Bearer <key>`.
  3. Call https://api.clod.io/v1/chat/completions with one of the officially listed free model ids.
api_key_url: "https://app.clod.io"
limits:
  requests:
    day: 100
---

CLōD (CLōD for AI agents) advertises 8 free models, 100 requests/day, no card, forever, with automatic UTC-midnight replenishment. Verified 2026-11-20.

**Free Tier:**

- 100 free requests/day, no card, auto-replenishing daily (UTC midnight reset). Frontmatter records the 100 RPD cap.
- Account + API key required. No payment method for the base free tier.
- Any purchase >= $25 unlocks 1,000 free requests/day forever; that paid-gated upgrade is not the basis for inclusion.

**Free Models:**

Official free list (display names from the marketing page): `meta-llama/Llama-4-Scout-17B-16E-Instruct`, `DeepSeek V3`, `Mistral 7B`, `Gemma 2 9B`, `Qwen 2.5 72B`, `Phi-4`, `Mixtral 8x7B`, `Yi-34B`.

The four catalog leads (`Gemma 4 31B IT`, `GPT OSS 120B`, `GPT OSS 20B`, `Qwen 3.5 9B`) are friendly names and are **not verified** as exact API model ids.

**Limits:**

- No token quota published. Do not infer one.

**Notes:**

- The live model list is auth-gated/SPA and could not be independently parsed; exact API ids for 7 of 8 models, context windows, and tool/vision support are unverified.
- Do not build model cards from these leads until authenticated `GET /v1/models` confirms the exact ids.

**Sources**

- https://clod.io/ai
- https://clod.io/free-cheap-ai
- docs/free-tier-research/raw/freellmapi-catalog/platforms/clod.json (discovery lead, verified 2026-11-20)
