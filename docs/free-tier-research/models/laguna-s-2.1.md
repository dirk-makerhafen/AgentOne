---
name: Poolside Laguna S 2.1
developer: Poolside
canonical_id: poolside/laguna-s-2.1
family: laguna
leaderboard_id: laguna-s-2.1
leaderboard_rank: 79
context_window: 1000000
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

Laguna S 2.1 is Poolside's frontier-class agentic-coding MoE model (118B total / 8B active). Weights are openly available under the permissive OpenMDW-1.1 license (commercial use allowed) for self-hosting. S 2.1 is text-to-text only (no vision inputs) with off/max thinking settings. Sibling size: [Laguna XS 2.1](laguna-xs-2.1.md).

**Capabilities:**

- Frontier-class agentic coding (per poolside.ai), 118B total / 8B active MoE.
- 1M-token context window.
- Native reasoning (thinking off/max per request), tool/function calling.
- Text-to-text only — no vision inputs.

**Notes:**

- Free use inputs/outputs may be used for training (per poolside.ai).
- License correction: weights are under OpenMDW-1.1 (permissive, commercial use allowed) — not Apache 2.0 as previously stated.
- Pollinations lists a bare `laguna` ID with equivalence to the Laguna family explicitly unverified in its provider file — not claimed as this model.
- Sibling size [Laguna XS 2.1](laguna-xs-2.1.md) is a separate leaderboard entry (`laguna-xs-2.1`) with its own free-availability rows.

**Sources**

- https://poolside.ai/models
- https://poolside.ai/blog/introducing-laguna-s-2-1 (official: 118B/8B MoE, 1M context, OpenMDW-1.1, text-only, off/max thinking)
- https://huggingface.co/poolside/Laguna-S-2.1 (official weights, license)
- https://docs.poolside.ai/api/overview
- https://kenari.id/v1/models (live catalog queried 2026-09-05: `:free` IDs with `"free": true`)
- https://aihubmix.com/models/free (`laguna-s-2.1-free` $0/M row)
- https://openrouter.ai/api/v1/models (live `:free` roster)
- https://portal.nousresearch.com/models (live FREE rows, checked 2026-09-05)
