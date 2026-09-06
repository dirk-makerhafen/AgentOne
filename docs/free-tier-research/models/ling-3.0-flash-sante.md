---
name: Ling 3.0 Flash Sante
developer: inclusionAI
canonical_id: inclusionai/ling-3.0-flash-sante
leaderboard_rank_estimated: "~85"
family: ling
context_window: 262144
max_output_tokens: 32768
reasoning: true
tool_call: true
modalities:
  input: [text]
  output: [text]
open_weights: true
providers:
  - name: Kilo Code
    file: kilo-code
    model_id: inclusionai/ling-3.0-flash-sante:free
    conditions: "Standing `:free` lane; anonymous keyless access allowed (200 req/hour/IP); authenticated free-model limits unpublished"
    verified: "2026-09-05"
  - name: OpenRouter
    file: openrouter
    model_id: inclusionai/ling-3.0-flash-sante:free
    conditions: "Free `:free` variant; account + key, no card; best-effort (paid traffic prioritized, 429s possible)"
    verified: "2026-09-05"
---

Ling 3.0 Flash Sante is inclusionAI's (Ant Group) health-and-medicine-specialized Mixture-of-Experts model: 124B total parameters with 5.1B activated, built by continued training of Ling 3.0 Flash for medical knowledge reasoning, clinical safety, evidence-based retrieval, and long-horizon medical workflows while retaining general reasoning, coding, and agentic capabilities. Released Sep 4 2026. The official model card states a 256K context window; API catalogs expose 262,144 tokens (frontmatter uses the catalog value).

**Capabilities:**

- Reasoning (thinking mode; medical knowledge reasoning and long-horizon medical tasks per the OpenRouter model page).
- Native function calling via tools/`tool_choice`; reported to not enforce structured output via `response_format` (OpenRouter model page FAQ).
- Text in / text out; 262,144 context, 32,768 max output (OpenRouter model page).
- Open weights (MIT license on the Ling family track, same 124B/5.1B base as the Fin sibling; downloadable checkpoints plus community quantizations).

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Kilo Code](../providers/kilo-code.md) | `inclusionai/ling-3.0-flash-sante:free` | Standing `:free` lane; anonymous keyless access allowed | 200 req/hour per IP anonymous; authenticated free-model limits unpublished | 2026-09-05 |
| [OpenRouter](../providers/openrouter.md) | `inclusionai/ling-3.0-flash-sante:free` | Free `:free` variant; account + key, no card | None combo-specific; provider-wide free-variant caps apply (see provider file) | 2026-09-05 |

**Notes:**

- Separate card from the sibling [Ling 3.0 Flash Fin](ling-3.0-flash-fin.md) (finance specialization); the two share the 124B/5.1B Ling 3.0 Flash base but diverge in free availability (Fin has a third free lane on OpenCode Zen; no third Sante lane is verified).
- Knowledge cutoff is unpublished — omitted.
- Temperature: not verified against Sante-specific official sources — omitted (unlike the Fin card, which cites its own model card).
- The Hugging Face `inclusionAI/Ling-3.0-flash-Sante` repo required authentication at check time (401); the MIT/open-weights claim follows the family's published licensing track (base Ling-3.0-flash and Fin sibling cards) — re-verify the Sante weights repo directly.
- No `limits` in frontmatter: no combo-specific numerics are documented for either row; provider-wide defaults stay in the provider files.
- `leaderboard_rank_estimated: "~85"` (2026-09-05): no `leaderboard.csv` entry. Basis: same shared Ling-3.0-Flash base (124B/5.1B) as the Fin sibling — AA Intelligence Index ~38, reported level with MiMo-V2.5 (CSV rank 99) and Qwen3.6-27B (CSV rank 67); midpoint placement, directional only.

**Sources**

- https://openrouter.ai/inclusionai/ling-3.0-flash-sante:free (262,144 context, 32,768 max output, tools/tool_choice yes, no response_format, 124B/5.1B MoE, released Sep 4 2026)
- https://vercel.com/ai-gateway/models/ling-3.0-flash-sante (256,000 context, 32,000 max output, function calling, health/medicine specialization)
- https://huggingface.co/inclusionAI/Ling-3.0-flash (base model card, MIT family track, 124B/5.1B hybrid MoE)
- https://huggingface.co/inclusionAI/Ling-3.0-flash-Fin (sibling card: MIT license, finance continued-training pattern)
- https://api.kilo.ai/api/gateway/models (live catalog `:free` row, 262144 context — free-route figure)
