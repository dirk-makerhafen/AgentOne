---
name: AMD Radeon Cloud Token Factory
url: https://developer.amd.com.cn/radeon/tokenfactory
api_base: https://developer.amd.com.cn/radeon/api/v1
setup_instructions: '1. Sign in at https://developer.amd.com.cn/radeon/tokenfactory
  and open Token Factory.

  2. Copy your `rc-` API key.

  3. Call GET /v1/models to see the current experimental roster.

  4. Use POST /v1/chat/completions (or /v1/messages for Anthropic-compatible clients).
  No GPU instance is needed and no credits are spent.

  '
api_key_url: https://developer.amd.com.cn/radeon/tokenfactory
---

AMD Radeon Cloud Token Factory is a free shared-model API on AMD's China developer site. AMD account + `rc-` key required, no payment. Verified 2026-11-20. **China site only.**

**Sources**

- https://amd-aim.github.io/radeon-cloud-docs/api/overview
- https://amd-aim.github.io/radeon-cloud-docs/api/rate-limits/
- https://developer.amd.com.cn/radeon/tokenfactory
- docs/free-tier-research/raw/freellmapi-catalog/platforms/radeon.json (discovery lead, verified 2026-11-20)
