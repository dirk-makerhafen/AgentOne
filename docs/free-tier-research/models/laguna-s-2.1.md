---
name: Poolside Laguna S 2.1
developer: Poolside
canonical_id: poolside/laguna-s-2.1
family: laguna
leaderboard_id: laguna-s-2.1
context_window: 1000000
reasoning: true
tool_call: true
temperature: true
modalities:
  input: [text]
  output: [text]
open_weights: true
providers:
  - name: Poolside
    file: poolside
    model_id: poolside/laguna-s-2.1
    conditions: "Free for a limited time (time-boxed promo, no end date); account + key; promo can end without notice"
    verified: "2026-09-05"
  - name: Kilo Code
    file: kilo-code
    model_id: poolside/laguna-s-2.1:free
    conditions: "Documented :free rows (representative, verify live)"
    verified: "2026-09-05"
  - name: Kenari
    file: kenari
    model_id: laguna-s-2-1:free
    conditions: "`:free` lane billed Rp 0 (live-catalog-observed 2026-09-05); account + key (`kn-...`), no top-up; confirm via GET /v1/models"
    verified: "2026-09-05"
  - name: AIHubMix
    file: aihubmix
    model_id: laguna-s-2.1-free
    conditions: "Free-model lane; account + key, no card; trial-use, 429s possible under load"
    verified: "2026-09-05"
  - name: OpenRouter
    file: openrouter
    model_id: poolside/laguna-s-2.1:free
    conditions: "Permanent `:free` variant; account + key, no card; free-model caps apply account-wide; roster rotates"
    verified: "2026-09-05"
  - name: Nous Portal
    file: nous-portal
    model_id: poolside/laguna-s-2.1
    conditions: "Standing $0 Free plan (Portal price FREE); account + key; paid duplicate routes exist — send the FREE-priced route"
    verified: "2026-09-05"
---

Laguna S 2.1 is Poolside's frontier-class agentic-coding MoE model (118B total / 8B active). Weights are openly available under the permissive OpenMDW-1.1 license (commercial use allowed) for self-hosting. S 2.1 is text-to-text only (no vision inputs) with off/max thinking settings. Sibling size: [Laguna XS 2.1](laguna-xs-2.1.md).

**Capabilities:**

- Frontier-class agentic coding (per poolside.ai), 118B total / 8B active MoE.
- 1M-token context window.
- Native reasoning (thinking off/max per request), tool/function calling.
- Text-to-text only — no vision inputs.

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Poolside](../providers/poolside.md) | `poolside/laguna-s-2.1` | Free for a limited time (time-boxed promo, no end date); account + key | None published; promo can end without notice | 2026-09-05 |
| [Kilo Code](../providers/kilo-code.md) | `poolside/laguna-s-2.1:free` | Documented `:free` rows (representative, verify live) | See provider file | 2026-09-05 |
| [Kenari](../providers/kenari.md) | `laguna-s-2-1:free` | `:free` lane billed Rp 0; account + key (`kn-...`), no top-up | None published combo-specific; per-minute caps + tiered daily quotas apply (see provider file); confirm via `GET /v1/models` before use | 2026-09-05 |
| [AIHubMix](../providers/aihubmix.md) | `laguna-s-2.1-free` | Free-model lane; account + key, no card | None published; free versions are trial-use (limited resources, 429s possible under load) | 2026-09-05 |
| [OpenRouter](../providers/openrouter.md) | `poolside/laguna-s-2.1:free` | Permanent `:free` variant; account + key, no card | None published combo-specific; provider-wide free-model caps apply (see provider file); roster rotates | 2026-09-05 |
| [Nous Portal](../providers/nous-portal.md) | `poolside/laguna-s-2.1` | Standing $0 Free plan (Portal price FREE); account + key | None published combo-specific; provider-wide Free limits apply (see provider file); send the FREE-priced route, not the paid duplicate | 2026-09-05 |

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
