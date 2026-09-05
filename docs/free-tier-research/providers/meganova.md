---
name: MegaNova
url: "https://meganova.ai"
setup_instructions: |
  1. Register a free Tier 1 account (no credit card required).
  2. Create an API key.
  3. Call the OpenAI-compatible API at https://api.meganova.ai/v1 with the key and a free-access model.
api_key_url: "https://meganova.ai"
limits: {}
---

MegaNova is a model gateway with a free Tier 1 (registration only, no card): free-access models under 100B parameters with per-model daily/request rate bands.

**Free Tier:**

- Tier 1: free registration, no credit card, max $20 credit purchase.
- Free-access models (<100B, including Manta Mini) at no cost; paid models unavailable on Tier 1.
- Tier 2+ ($1 deposit and up) unlocks more, including free DeepSeek V3 at 100 RPD.

**Free Models:**

- Free-access pool (<100B, verify live): includes Manta Mini and rotating sub-100B models; one observed free row is `mistralai/Mistral-Small-3.2-24B-Instruct-2506`.
- Paid-model RPD quotas do not apply on Tier 1.

**Limits:**

- Documented as ranges (operator-set, verify live): free-model RPD 50–500, RPM 20–200 on Tier 1.
- No single numeric figure is published; frontmatter limits omitted deliberately.

**Notes:**

- Account required; API key required; no card for Tier 1.
- Endpoint `https://api.meganova.ai/v1` is fixture-reported; confirm against the official docs before use.

**Sources**

- https://docs.meganova.ai/tiers.md (tier table verified 2026-09-05)
