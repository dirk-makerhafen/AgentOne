---
name: Poolside Laguna (family)
developer: Poolside
canonical_id: poolside/laguna
family: laguna
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
    model_id:
      - poolside/laguna-s-2.1
      - poolside/laguna-xs-2.1
    conditions: "Free for a limited time (time-boxed promo, no end date); account + key; promo can end without notice"
    verified: "2026-09-05"
  - name: Requesty
    file: requesty
    model_id:
      - poolside/laguna-xs.2
      - poolside/laguna-m.1
    conditions: "Free-models tier ('free for now'); account + key, no card; quota shared across all free models combined"
    limits:
      requests:
        minute: 20
        day: 200
    verified: "2026-09-05"
  - name: Kilo Code
    file: kilo-code
    model_id:
      - poolside/laguna-s-2.1:free
      - poolside/laguna-xs-2.1:free
    conditions: "Documented :free rows (representative, verify live)"
    verified: "2026-09-05"
---

Laguna is Poolside's family of open agentic-coding MoE models. Versions differ per host, so this is a family card — see the versions table. Weights are openly available (Apache 2.0 track) for self-hosting.

**Versions (fixture-reported; verify live):**

| Version | Size | Context | Notes |
|---|---|---|---|
| `laguna-s-2.1` | 118B total / 8B active MoE | 1M | Frontier-class agentic coding (per poolside.ai) |
| `laguna-xs-2.1` | 33B total / 3B active MoE | 256K | Light/fast agentic coding (per poolside.ai) |
| `laguna-xs.2` | XS class | 262K | Older row served by third-party routers |
| `laguna-m.1` | M class | — | Older row served by third-party routers |

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Poolside](../providers/poolside.md) | `poolside/laguna-s-2.1`, `poolside/laguna-xs-2.1` | Free for a limited time (time-boxed promo, no end date); account + key | None published; promo can end without notice | 2026-09-05 |
| [Requesty](../providers/requesty.md) | `poolside/laguna-xs.2`, `poolside/laguna-m.1` | Free-models tier ("free for now"); account + key, no card | New orgs: 200 req/day + 20 req/min shared across all free models combined | 2026-09-05 |
| [Kilo Code](../providers/kilo-code.md) | `poolside/laguna-s-2.1:free`, `poolside/laguna-xs-2.1:free` | Documented `:free` rows (representative, verify live) | See provider file | 2026-09-05 |

**Notes:**

- Free use inputs/outputs may be used for training (per poolside.ai).

**Sources**

- https://poolside.ai/models
- https://docs.poolside.ai/api/overview
- https://docs.requesty.ai/features/free-models
- raw/opencode-models-api/poolside/model_laguna-xs-2.1.json (capabilities/context — discovery data)
