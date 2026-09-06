---
name: MegaNova
url: "https://meganova.ai"
setup_instructions: |
  1. Register a free Tier 1 account (no credit card required) via the console at https://console.meganova.ai.
  2. An API key is auto-generated at account creation; view or renew it in the user dashboard (inference keys start with `sk-`).
  3. Call the OpenAI-compatible Inference API at https://api.meganova.ai/v1 with `Authorization: Bearer <key>` and a free-quota model ID.
api_key_url: "https://console.meganova.ai"
limits: {}
---

MegaNova is a model gateway with a free Tier 1 (registration only, no card): free-quota models with per-model daily quotas (per account, reset 00:00 UTC) and tier-scoped rate bands.

**Free Tier:**

- Tier 1: free registration, no credit card, max $20 credit purchase.
- Free-quota models at no cost on Tier 1 (per-model daily quotas below); paid models unavailable on Tier 1.
- Tier 2+ ($1 deposit and up) unlocks more, including free DeepSeek V3 at 100 RPD (200 RPD on Tier 4).

**Free Models (Tier 1 daily quotas, per free-model-quota doc verified 2026-09-05):**

- `mistralai/Mistral-Small-3.2-24B-Instruct-2506` — 24B text model, Tier 1 free quota 50 requests/day (Tier 2/3 = 300, Tier 4 = 1,000).
- `meganova-ai/manta-mini-1.0` — Tier 1 free quota 50/day (Tier 2/3 = 500, Tier 4 = 1,000).
- `meganova-ai/manta-flash-1.0` — Tier 1 free quota 50/day (Tier 2/3 = 500, Tier 4 = 1,000).
- `Steelskull/L3.3-MS-Nevoria-70b` — 70B text model, Tier 1 free quota 50/day (Tier 2/3 = 300, Tier 4 = 1,000).
- `Sao10K/L3-70B-Euryale-v2.1` — 70B text model, Tier 1 free quota 50/day (Tier 2/3 = 300, Tier 4 = 1,000).
- `Sao10K/L3-8B-Stheno-v3.2` — 8B text model, Tier 1 free quota 50/day (Tier 2/3 = 500, Tier 4 = 1,000).
- `BruhzWater/Sapphira-L3.3-70b-0.1` — 70B text model, Tier 1 free quota 50/day (Tier 2/3 = 300, Tier 4 = 1,000).
- `FallenMerick/MN-Violet-Lotus-12B` — 12B text model, Tier 1 free quota 50/day (Tier 2/3 = 500, Tier 4 = 1,000).
- `Qwen/Qwen3-Embedding-8B` — embedding model, Tier 1 free quota 50/day (Tier 2 = 500, Tier 3 = 2,000, Tier 4 = 5,000).
- `BAAI/bge-reranker-v2-m3` — reranker, Tier 1 free quota 50/day (Tier 2/3 = 500, Tier 4 = 1,000).
- Not free at Tier 1 (quota 0, need Tier 2+): `meganova-ai/manta-pro-1.0`, `Systran/faster-whisper-large-v3`, `zai-org/GLM-4.7-Flash` (Tier 2 = 50, Tier 3/4 = 100).
- Once free quota is exhausted, usage continues as paid only if the "allow paid usage after free quota" switch is on.

**Limits:**

- Tier comparison table (verified 2026-09-05): Tier 1 free-model RPD range 50–500, RPM range 20–200 (operator-set bands, not single figures).
- Tier 1 detail page states a flat 60 RPM and 200,000 TPM — this disagrees with the comparison table's 20–200 RPM range, so no single number is put in frontmatter; treat 60 RPM / 200K TPM as Tier-1-page-reported and the ranges as the tier-table position.
- Frontmatter limits omitted deliberately: quotas are per-model (belong in the body), and no single provider-wide numeric is unambiguous.

**Notes:**

- Account required; API key required; no card for Tier 1.
- Endpoint `https://api.meganova.ai/v1` verified in inference docs (the old `https://inference.meganova.ai/v1` base URL is deprecated but still works).
- None of the catalog's model cards is free on MegaNova Tier 1 (verified against the current `models/` catalog): `GLM-4.7-Flash` (card `glm-4.7-flash`) has Tier 1 quota 0 and needs a Tier 2 $1 deposit — do not link it as a free row.
- Doc discrepancy (verified 2026-09-05): the Tier 1 detail page lists `Faster-Whisper-Large-V3` at 50 RPD, but the free-model-quota doc (the specialized quota source) lists Tier 1 = 0; quota-doc values are used above.
- Full live catalog (IDs, prices, context, per-tier daily limits) at https://console.meganova.ai/serverless and via authenticated `GET https://api.meganova.ai/v1/models`.

**Sources**

- https://docs.meganova.ai/tiers.md (tier table verified 2026-09-05)
- https://docs.meganova.ai/tiers/tier-1.md (Tier 1 detail: RPM/TPM, model list, verified 2026-09-05)
- https://docs.meganova.ai/free-model-quota (per-model daily quotas, verified 2026-09-05)
- https://docs.meganova.ai/inference-models/model-list (catalog location, `Free` filter, verified 2026-09-05)
- https://docs.meganova.ai/api-reference/inference-models (`https://api.meganova.ai/v1` base URL, deprecation note)
- https://docs.meganova.ai/faq/api-technical-specifications (dashboard `sk-` key, chat/completions endpoint)
- https://docs.meganova.ai/api-reference (keys auto-generated at account creation, renewed in dashboard)
