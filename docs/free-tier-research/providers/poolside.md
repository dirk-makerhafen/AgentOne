---
name: Poolside
url: "https://poolside.ai"
setup_instructions: |
  1. Get an API key at https://platform.poolside.ai.
  2. Point an OpenAI-compatible client at base URL https://inference.poolside.ai/v1 with the key.
  3. Call with model `poolside/laguna-s-2.1` or `poolside/laguna-xs-2.1`.
api_key_url: "https://platform.poolside.ai"
limits: {}
---

Poolside trains its own Laguna coding models and serves them via an OpenAI-compatible API that is "free to use for a limited time" (time-boxed promo, no end date published).

**Free Tier:**

- Laguna API free for a limited time; account + API key required.
- Weights are also openly available (Hugging Face, OpenMDW→Apache 2.0 licenses) for self-hosting.

**Free Models:**

- `poolside/laguna-s-2.1` — frontier-class agentic coding, 118B total / 8B active MoE, 1M context.
- `poolside/laguna-xs-2.1` — light/fast agentic coding, 33B total / 3B active MoE, 256K context.
- Older `laguna-m.1` / `laguna-xs.2` rows appear on third-party free routers (verify live).

**Limits:**

- Published numerics: none; promo can end without notice.

**Notes:**

- Data use: "if you use Laguna for free, we may use inputs/outputs to train."
- Same models are already served free via third-party routers (OpenRouter/Requesty/Nous free rows).

**Sources**

- https://poolside.ai/models ("Free to use for a limited time" verified 2026-09-05)
- https://docs.poolside.ai/api/overview
