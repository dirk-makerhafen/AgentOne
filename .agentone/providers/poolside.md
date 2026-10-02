---
name: Poolside
url: "https://poolside.ai"
api_base: "https://inference.poolside.ai/v1"
setup_instructions: |
  1. Sign in to https://platform.poolside.ai, open the API Keys tab, and click New key.
  2. Point an OpenAI-compatible client at base URL https://inference.poolside.ai/v1 with the key as a Bearer token.
  3. Call with model `poolside/laguna-s-2.1` or `poolside/laguna-xs-2.1`.
api_key_url: "https://platform.poolside.ai"
limits: {}
---

Poolside trains its own Laguna coding models and serves them via an OpenAI-compatible API that is "free to use for a limited time" (time-boxed promo, still current with no end date published as of 2026-09-05).

**Free Tier:**

- Laguna API free for a limited time; account + API key required. The promo can end without notice — Poolside publishes no pricing page and no first-party rate card.
- Weights are also openly available on Hugging Face for self-hosting (Laguna S 2.1 and XS 2.1 under OpenMDW-1.1; older Laguna M.1 under Apache 2.0).

**Free Models:**

- [`poolside/laguna-s-2.1`](../models/laguna-s-2.1.md) — frontier-class agentic coding, 118B total / 8B active MoE, 1M context, native reasoning (thinking on/off per request).
- [`poolside/laguna-xs-2.1`](../models/laguna-xs-2.1.md) — light/fast agentic coding, 33B total / 3B active MoE, 256K context, native reasoning.
- Older `laguna-m.1` (225B/23B, 256K) / `laguna-xs.2` rows appear on third-party free routers (verify live).

**Limits:**

- Published numerics from Poolside: none; no RPM/RPD/TPM figures documented.

**Notes:**

- Training-data use ("if you use Laguna for free, we may use inputs/outputs to train") appears on OpenRouter's `:free` listings for these models, not in Poolside's own docs — attribute it to the router row, not to Poolside's first-party API.
- Same models are served free via third-party routers (OpenRouter/Requesty/Nous free rows); router rows carry their own rate limits and data-use terms.
- Poolside publishes no rate card; quoted paid prices elsewhere (e.g. $0.10 in / $0.20 out) come from the OpenRouter listing, not from Poolside.

**Sources**

- https://poolside.ai/models ("Free to use for a limited time", model IDs, weights links — verified 2026-09-05)
- https://docs.poolside.ai/api/overview (base URL, endpoints, key steps)
- https://docs.poolside.ai/get-started/supported-models (parameters, context windows, licenses)
- https://openrouter.ai/poolside/laguna-s-2.1:free (third-party free-row training-data notice)
