---
name: MegaNova
url: https://meganova.ai
api_base: https://api.meganova.ai/v1
setup_instructions: '1. Register a free Tier 1 account (no credit card required) via
  the console at https://console.meganova.ai.

  2. An API key is auto-generated at account creation; view or renew it in the user
  dashboard (inference keys start with `sk-`).

  3. Call the OpenAI-compatible Inference API at https://api.meganova.ai/v1 with `Authorization:
  Bearer <key>` and a free-quota model ID.

  '
api_key_url: https://console.meganova.ai
---

MegaNova is a model gateway with a free Tier 1 (registration only, no card): free-quota models with per-model daily quotas (per account, reset 00:00 UTC) and tier-scoped rate bands.

**Sources**

- https://docs.meganova.ai/tiers.md (tier table verified 2026-09-05)
- https://docs.meganova.ai/tiers/tier-1.md (Tier 1 detail: RPM/TPM, model list, verified 2026-09-05)
- https://docs.meganova.ai/free-model-quota (per-model daily quotas, verified 2026-09-05)
- https://docs.meganova.ai/inference-models/model-list (catalog location, `Free` filter, verified 2026-09-05)
- https://docs.meganova.ai/api-reference/inference-models (`https://api.meganova.ai/v1` base URL, deprecation note)
- https://docs.meganova.ai/faq/api-technical-specifications (dashboard `sk-` key, chat/completions endpoint)
- https://docs.meganova.ai/api-reference (keys auto-generated at account creation, renewed in dashboard)
