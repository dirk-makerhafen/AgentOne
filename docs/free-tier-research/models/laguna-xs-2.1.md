---
name: Poolside Laguna XS 2.1
developer: Poolside
canonical_id: poolside/laguna-xs-2.1
family: laguna
leaderboard_id: laguna-xs-2.1
context_window: 262144
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
    model_id: poolside/laguna-xs-2.1
    conditions: "Free for a limited time (time-boxed promo, no end date); account + key; promo can end without notice"
    verified: "2026-09-05"
  - name: Requesty
    file: requesty
    model_id: poolside/laguna-xs.2
    conditions: "Free-models tier ('free for now'); account + key, no card; quota shared across all free models combined"
    limits:
      requests:
        minute: 20
        day: 200
    verified: "2026-09-05"
  - name: Kilo Code
    file: kilo-code
    model_id: poolside/laguna-xs-2.1:free
    conditions: "Documented :free rows (representative, verify live)"
    verified: "2026-09-05"
  - name: Kenari
    file: kenari
    model_id: laguna-xs-2-1:free
    conditions: "`:free` lane billed Rp 0 (live-catalog-observed 2026-09-05); account + key (`kn-...`), no top-up; confirm via GET /v1/models"
    verified: "2026-09-05"
  - name: AIHubMix
    file: aihubmix
    model_id: laguna-xs-2.1-free
    conditions: "Free-model lane; account + key, no card; trial-use, 429s possible under load"
    verified: "2026-09-05"
  - name: OpenRouter
    file: openrouter
    model_id: poolside/laguna-xs-2.1:free
    conditions: "Permanent `:free` variant; account + key, no card; free-model caps apply account-wide; roster rotates"
    verified: "2026-09-05"
  - name: Nous Portal
    file: nous-portal
    model_id: poolside/laguna-xs-2.1
    conditions: "Standing $0 Free plan (Portal price FREE); account + key; paid duplicate routes exist — send the FREE-priced route"
    verified: "2026-09-05"
---

Laguna XS 2.1 is Poolside's light/fast agentic-coding MoE model (33B total / 3B active, 256K context — routers expose 262144). Weights are openly available under the permissive OpenMDW-1.1 license (commercial use allowed) for self-hosting. Sibling size: [Laguna S 2.1](laguna-s-2.1.md).

**Capabilities:**

- Light/fast agentic coding (per poolside.ai), 33B total / 3B active MoE.
- 256K context (router catalogs expose 262144).
- Native reasoning, tool/function calling.

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Poolside](../providers/poolside.md) | `poolside/laguna-xs-2.1` | Free for a limited time (time-boxed promo, no end date); account + key | None published; promo can end without notice | 2026-09-05 |
| [Requesty](../providers/requesty.md) | `poolside/laguna-xs.2` | Free-models tier ("free for now"); account + key, no card | New orgs: 200 req/day + 20 req/min shared across all free models combined | 2026-09-05 |
| [Kilo Code](../providers/kilo-code.md) | `poolside/laguna-xs-2.1:free` | Documented `:free` rows (representative, verify live) | See provider file | 2026-09-05 |
| [Kenari](../providers/kenari.md) | `laguna-xs-2-1:free` | `:free` lane billed Rp 0; account + key (`kn-...`), no top-up | None published combo-specific; per-minute caps + tiered daily quotas apply (see provider file); confirm via `GET /v1/models` before use | 2026-09-05 |
| [AIHubMix](../providers/aihubmix.md) | `laguna-xs-2.1-free` | Free-model lane; account + key, no card | None published; free versions are trial-use (limited resources, 429s possible under load) | 2026-09-05 |
| [OpenRouter](../providers/openrouter.md) | `poolside/laguna-xs-2.1:free` | Permanent `:free` variant; account + key, no card | None published combo-specific; provider-wide free-model caps apply (see provider file); roster rotates | 2026-09-05 |
| [Nous Portal](../providers/nous-portal.md) | `poolside/laguna-xs-2.1` | Standing $0 Free plan (Portal price FREE); account + key | None published combo-specific; provider-wide Free limits apply (see provider file); send the FREE-priced route, not the paid duplicate | 2026-09-05 |

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
