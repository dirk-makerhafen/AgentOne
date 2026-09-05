---
name: LFM 2.5 2.6B
developer: Liquid AI
canonical_id: liquid/lfm-2.5-2.6b
leaderboard_id: lfm-2.5-2.6b
family: lfm
context_window: 131072
reasoning: true
tool_call: true
modalities:
  input: [text]
  output: [text]
open_weights: true
providers:
  - name: Kilo Code
    file: kilo-code
    model_id: liquid/lfm-2.5-2.6b:free
    conditions: "Standing `:free` lane; anonymous keyless access allowed, no account/key/card; roster rotates"
    context_window: 65536
    verified: "2026-09-05"
  - name: OpenRouter
    file: openrouter
    model_id: liquid/lfm-2.5-2.6b:free
    conditions: "Permanent `:free` variant; account + key, no card; free-model caps apply account-wide; roster rotates"
    verified: "2026-09-05"
---

LFM 2.5 2.6B is Liquid AI's dense 2.6B-parameter (2.69B total, 30-layer hybrid: 22 double-gated short-convolution blocks + 8 grouped-query-attention layers) on-device agentic model, released Aug 4 2026. It is trained for planning, tool calling, and multi-step agent tasks inside real harnesses (Hermes Agent, OpenClaw, Pi) and runs in under 2.5 GB of memory.

**Capabilities:**

- Agentic workloads: plans, calls tools natively, and runs multi-step tasks (official docs and blog; base + instruction-tuned checkpoints).
- Native tool calling for on-device agents (official docs page).
- Reasoning before answering (catalog-reported, consistent across catalogs).
- Text in / text out; 16 languages; 131,072-token context via a dedicated mid-training extension phase (official docs and model card).
- Open weights (base + post-trained checkpoints, plus GGUF/MLX/ONNX formats) under the LFM Open License v1.0 — Apache-2.0-based but NOT Apache 2.0: free commercial use only under $10M annual revenue, otherwise a commercial license from Liquid AI is required; attribution required, no copyleft.

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Kilo Code](../providers/kilo-code.md) | `liquid/lfm-2.5-2.6b:free` | Standing `:free` lane; anonymous keyless access allowed | 200 req/hour per IP anonymous; authenticated free-model limits unpublished; Kilo serves a 64K-context variant (see override) | 2026-09-05 |
| [OpenRouter](../providers/openrouter.md) | `liquid/lfm-2.5-2.6b:free` | Free `:free` variant; account + key, no card | None combo-specific; provider-wide free-variant caps apply (see provider file) | 2026-09-05 |

**Notes:**

- The Kilo Code entry carries a `context_window: 65536` override: Kilo's live catalog exposes this row at 64K context, half the official 131,072 figure. Design long-context use against the endpoint actually called.
- No `limits` in frontmatter: no combo-specific numerics are documented for either row; provider-wide defaults stay in the provider files.
- Max output tokens: one catalog claims 8K — single-source, unverified — omitted.
- Knowledge cutoff is unpublished — omitted.
- License is the load-bearing caveat: `open_weights: true` means downloadable/fine-tunable weights, but commercial deployment at or above $10M revenue needs a Liquid AI commercial license (per the official LFM License page).

**Sources**

- https://docs.liquid.ai/lfm/models/lfm25-2-6b (official: 128K context, native tool calling, agentic/harness positioning)
- https://www.liquid.ai/blog/lfm2-5-2-6b (official: on-device agent, 220 tok/s, open weights)
- https://huggingface.co/LiquidAI/LFM2.5-2.6B (official: 131,072 context, ~34T tokens, hybrid architecture, LFM license)
- https://www.liquid.ai/lfm-license (official: LFM Open License 1.0, $10M revenue threshold, attribution, no copyleft)
- https://api.kilo.ai/api/gateway/models (live catalog `:free` row, 64K context — free-route figure, motivates the override)
- https://openrouter.ai/api/v1/models (live `:free` roster)
