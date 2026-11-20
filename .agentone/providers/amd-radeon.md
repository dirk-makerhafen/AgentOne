---
name: AMD Radeon Cloud Token Factory
url: "https://developer.amd.com.cn/radeon/tokenfactory"
api_base: "https://developer.amd.com.cn/radeon/api/v1"
setup_instructions: |
  1. Sign in at https://developer.amd.com.cn/radeon/tokenfactory and open Token Factory.
  2. Copy your `rc-` API key.
  3. Call GET /v1/models to see the current experimental roster.
  4. Use POST /v1/chat/completions (or /v1/messages for Anthropic-compatible clients). No GPU instance is needed and no credits are spent.
api_key_url: "https://developer.amd.com.cn/radeon/tokenfactory"
limits:
  requests:
    minute: 20
---

AMD Radeon Cloud Token Factory is a free shared-model API on AMD's China developer site. AMD account + `rc-` key required, no payment. Verified 2026-11-20. **China site only.**

**Free Tier:**

- Free shared models do not consume credits and require no GPU instance. A separate "Model service endpoints" product does consume credits and is not this tier.
- Typical documented limits (dynamic; read response headers): 20 RPM per account on the gateway (60s sliding window), 30 RPM per key and 120 RPM per IP at platform admission, 8 concurrent per key, plus a daily cap in Token Factory points (Beijing-time day, resets 00:00 UTC+8).
- `X-RateLimit-*` headers are authoritative; `-USD`-named headers report points, not money. `429` includes `Retry-After` (60s per-minute, 1s concurrency).

**Free Models:**

- Official catalog page names (exact wire ids require authenticated `GET /v1/models`): DeepSeek-V4-Flash, DeepSeek-V4-Flash-Vision-Exp, DeepSeek-V4.1-Flash, Qwen3.8-27B, GLM-5.3-Flash, MiMo-V2.6-Flash, MiniCPM5-2B, MiniCPM-V-4.7-1B / -35B-A3B, Gemma-4-31B-IT, MinerU2.5-Pro, OmniVoice, Clef, d3, d3-flash.
- Catalog-only `DeepSeek-V4-Flash` (1,048,576 context, tools) and `Qwen3.8-Flash-Next` are leads; the latter is absent from the official catalog, which names `Qwen3.8-27B` instead.
- Roster is experimental and rotates.

**Limits:**

- Frontmatter records the documented 20 RPM per-account gateway limit. Per-IP and concurrency limits are in the body because they cannot be expressed in the supported schema.

**Notes:**

- Gateway drops unknown parameters rather than erroring.
- Some models use non-chat paths (`/v1/audio/speech`, `/v1/ocr`).
- Model list and per-model context/capabilities cannot be verified without an account.

**Sources**

- https://amd-aim.github.io/radeon-cloud-docs/api/overview
- https://amd-aim.github.io/radeon-cloud-docs/api/rate-limits/
- https://developer.amd.com.cn/radeon/tokenfactory
- docs/free-tier-research/raw/freellmapi-catalog/platforms/radeon.json (discovery lead, verified 2026-11-20)
