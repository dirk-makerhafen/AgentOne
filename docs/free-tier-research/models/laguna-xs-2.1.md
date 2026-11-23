---
name: Poolside Laguna XS 2.1
developer: Poolside
canonical_id: poolside/laguna-xs-2.1
family: laguna
leaderboard_id: laguna-xs-2.1
leaderboard_rank: 235
context_window: 262144
reasoning: true
tool_call: true
temperature: true
modalities:
  input:
  - text
  output:
  - text
open_weights: true
---

Laguna XS 2.1 is Poolside's light/fast agentic-coding MoE model (33B total / 3B active, 256K context — routers expose 262144). Weights are openly available under the permissive OpenMDW-1.1 license (commercial use allowed) for self-hosting. Sibling size: [Laguna S 2.1](laguna-s-2.1.md).

**Capabilities:**

- Light/fast agentic coding (per poolside.ai), 33B total / 3B active MoE.
- 256K context (router catalogs expose 262144).
- Native reasoning, tool/function calling.

**Notes:**

- The Requesty row above is the older XS-class ID (`laguna-xs.2`); Requesty also serves `poolside/laguna-m.1` (M class) free, which has no leaderboard entry and no dedicated card — noted here as a re-verification lead, not a table row.
- Free use inputs/outputs may be used for training (per poolside.ai).
- License correction: weights are under OpenMDW-1.1 (permissive, commercial use allowed) — not Apache 2.0 as previously stated.
- Pollinations lists a bare `laguna` ID with equivalence to the Laguna family explicitly unverified in its provider file — not claimed as this model.
- Sibling size [Laguna S 2.1](laguna-s-2.1.md) is a separate leaderboard entry (`laguna-s-2.1`) with its own free-availability rows.

**Sources**

- https://poolside.ai/models
- https://docs.poolside.ai/api/overview
- https://docs.requesty.ai/features/free-models
- https://kenari.id/v1/models (live catalog queried 2026-09-05: `:free` IDs with `"free": true`)
- https://aihubmix.com/models/free (`laguna-xs-2.1-free` $0/M row)
- https://openrouter.ai/api/v1/models (live `:free` roster)
- https://portal.nousresearch.com/models (live FREE rows, checked 2026-09-05)
- raw/opencode-models-api/poolside/model_laguna-xs-2.1.json (capabilities/context — discovery data)
