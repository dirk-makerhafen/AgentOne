---
name: Ling 3.0 Flash Fin
developer: inclusionAI
canonical_id: inclusionai/ling-3.0-flash-fin
leaderboard_rank_estimated: "~85"
family: ling
context_window: 262144
max_output_tokens: 32768
reasoning: true
tool_call: true
temperature: true
modalities:
  input: [text]
  output: [text]
open_weights: true
providers:
  - name: Kilo Code
    file: kilo-code
    model_id: inclusionai/ling-3.0-flash-fin:free
    conditions: "Standing `:free` lane; anonymous keyless access allowed (200 req/hour/IP); authenticated free-model limits unpublished"
    verified: "2026-09-05"
  - name: OpenRouter
    file: openrouter
    model_id: inclusionai/ling-3.0-flash-fin:free
    conditions: "Free `:free` variant; account + key, no card; best-effort (paid traffic prioritized, 429s possible)"
    verified: "2026-09-05"
  - name: OpenCode Zen
    file: opencode-zen
    model_id: ling-3.0-flash-fin-free
    conditions: "Anonymous free pool; no account, key, or payment; limited-time free (feedback-collection period)"
    verified: "2026-09-05"
---

Ling 3.0 Flash Fin is inclusionAI's (Ant Group) finance-enhanced Mixture-of-Experts model: 124B total parameters with 5.1B activated, built by continued training of Ling 3.0 Flash on high-quality financial data for investment research, valuation, and long-horizon financial agent workflows. The official model card states a 256K context window; API catalogs expose 262,144 tokens (frontmatter uses the catalog value).

**Capabilities:**

- Reasoning (thinking mode enabled by default; `temperature` / `top_p` / `top_k` tunable per the official model card).
- Native function calling via tools/`tool_choice`; reported to not enforce structured output via `response_format` (catalog-reported).
- Text in / text out; 262,144 context, 32,768 max output (catalog-reported).
- Open weights (MIT license, downloadable checkpoints plus community quantizations).

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Kilo Code](../providers/kilo-code.md) | `inclusionai/ling-3.0-flash-fin:free` | Standing `:free` lane; anonymous keyless access allowed | 200 req/hour per IP anonymous; authenticated free-model limits unpublished | 2026-09-05 |
| [OpenRouter](../providers/openrouter.md) | `inclusionai/ling-3.0-flash-fin:free` | Free `:free` variant; account + key, no card | None combo-specific; provider-wide free-variant caps apply (see provider file) | 2026-09-05 |
| [OpenCode Zen](../providers/opencode-zen.md) | `ling-3.0-flash-fin-free` | Anonymous free pool; no account, key, or payment; limited-time free | None published; free pool enforced via `FreeUsageLimitError` (quota and reset window unknown) | 2026-09-05 |

**Notes:**

- Sibling `ling-3.0-flash-sante:free` is also free on Kilo Code and OpenRouter, but no third provider is verified — no row (re-verification lead only).
- Nous Portal lists Ling 3.0 Flash Fin in its Portal-price-FREE set, but its provider file publishes no exact `model` ID string — no row added until the ID is confirmed live at https://portal.nousresearch.com/models (re-verification lead).
- Knowledge cutoff is unpublished — omitted.
- While free on Opencode Zen, collected data may be used to improve the model (per the Zen provider file).
- `leaderboard_rank_estimated: "~85"` (2026-09-05): no `leaderboard.csv` entry. Basis: AA Intelligence Index ~38 for the shared Ling-3.0-Flash base (124B/5.1B), reported level with MiMo-V2.5 (CSV rank 94) and Qwen3.6-27B (CSV rank 64); midpoint placement, directional only.
- No `limits` in frontmatter: no combo-specific numerics are documented for any of the three rows; provider-wide defaults stay in the provider files.

**Sources**

- https://huggingface.co/inclusionAI/Ling-3.0-flash-Fin (official model card: developer, params, 256K context, MIT license, thinking mode, tool-use tag)
- https://huggingface.co/inclusionAI/Ling-3.0-flash (base model card)
- https://openrouter.ai/inclusionai/ling-3.0-flash-fin:free (262,144 context, 32,768 max output, free variant)
- https://developer.puter.com/ai/inclusionai/ling-3.0-flash-fin/ (function calling, no response_format enforcement — catalog-reported)
- https://api.kilo.ai/api/gateway/models (live catalog `:free` row, no auth)
- https://x.com/AntLingAGI/status/2093022087069958492 (release announcement, linked from official model card)
