---
name: Nemotron 3.5 Lightning 30B A3B
developer: Nvidia
canonical_id: nvidia/nemotron-3.5-lightning-30b-a3b
leaderboard_id: nemotron-3.5-lightning-30b-a3b
leaderboard_rank: 227
family: nemotron
context_window: 1048576
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
    model_id: nvidia/nemotron-3.5-lightning:free
    conditions: "Standing `:free` lane; anonymous keyless access allowed, no account/key/card; roster rotates"
    verified: "2026-09-05"
  - name: OpenRouter
    file: openrouter
    model_id: nvidia/nemotron-3.5-lightning:free
    conditions: "Permanent `:free` variant; account + key, no card; free-model caps apply account-wide; roster rotates"
    verified: "2026-09-05"
  - name: OpenCode Zen
    file: opencode-zen
    model_id: nemotron-3.5-lightning-free
    conditions: "Anonymous free pool; no account, key, or payment; limited-time free (feedback-collection period)"
    verified: "2026-09-05"
  - name: UnoRouter
    file: unorouter
    model_id: nemotron-3.5-lightning:free
    conditions: ":free lane; account + key, no card"
    limits:
      requests:
        minute: 1
    verified: "2026-09-05"
---

Nemotron 3.5 Lightning 30B A3B is Nvidia's efficiency-tuned 3.5-generation chat/reasoning model: a hybrid MoE (30B total / 3B active, Mamba-2 + MoE + Attention with Multi-Token Prediction) pre-trained on 20T+ tokens for agents, chatbots, RAG, and instruction following, with single-H100 deployability. It is a distinct 3.5-generation model — not the Nemotron 3 Nano ([Nemotron 3 Nano 30B A3B](nemotron-3-nano-30b-a3b.md)) despite the matching 30B/3B shape, and not the guardrail Nemotron 3.5 Content Safety model (a 4B specialist deliberately not catalogued).

**Capabilities:**

- Reasoning trace with configurable on/off via chat template (`enable_thinking=True/False`) (official model card).
- Tool/function calling (official training includes tool calling; serve recipes use the `qwen3_coder` tool-call parser with `--enable-auto-tool-choice`).
- Temperature control (official recommended sampling: temperature 1.0, top_p 0.95).
- Text in / text out (official model card: Input/Output Type Text).
- Up to 1M context (official model card; single-H100 BF16 serving is memory-bound to ~256K; Kilo free route lists 1M).
- Open weights (BF16 reference weights plus NVFP4, DFlash, and DSpark checkpoints on Hugging Face) under the OpenMDW License Agreement v1.1.

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Kilo Code](../providers/kilo-code.md) | `nvidia/nemotron-3.5-lightning:free` | Standing `:free` lane; anonymous keyless access allowed, no account/key/card | None published combo-specific; provider-wide anonymous `:free` quota applies (see provider file); roster rotates | 2026-09-05 |
| [OpenRouter](../providers/openrouter.md) | `nvidia/nemotron-3.5-lightning:free` | Permanent `:free` variant; account + key, no card | None published combo-specific; provider-wide free-model caps apply (see provider file); roster rotates | 2026-09-05 |
| [OpenCode Zen](../providers/opencode-zen.md) | `nemotron-3.5-lightning-free` | Anonymous free pool; no account, key, or payment; limited-time free | None published; free pool enforced via `FreeUsageLimitError` (quota and reset window unknown) | 2026-09-05 |
| [UnoRouter](../providers/unorouter.md) | `nemotron-3.5-lightning:free` | `:free` lane; account + key, no card | ~1 req/min per user + upstream caps (see provider file) | 2026-09-05 |

**Notes:**

- Context: the official model card states up to 1M tokens (validated at 1M on GB200/B200/8xH100; ~256K memory-bound on a single H100 BF16). The Kilo free-route catalog lists 1M — card default follows the official maximum, which matches the as-served free route.
- Nano lookalike: Lightning 3.5 shares the 30B-total/3B-active shape with Nemotron 3 Nano but is a separate 3.5-generation model (different architecture generation, training recipe, and release date 2026-08-11) — kept as its own card.
- The BF16 release is the customization/post-training reference; the NVFP4 release is the recommended deployment path (official model card) — irrelevant to free-API use but useful context.
- `max_output_tokens`: no official figure found — omitted.
- Knowledge cutoff: official docs give two dates (pre-training September 2025, post-training May 2026) with no single cutoff — omitted.
- Free-route data handling: NVIDIA free endpoints are trial-use only with session logging under NVIDIA API Trial Terms — do not submit personal or confidential data on free routes.

**Sources**

- https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16 (official: 30B/3B, Mamba+Transformer MoE + MTP, reasoning flag, tool calling, 1M context, text in/out, OpenMDW-1.1, 2026-08-11 release, cutoffs)
- https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b/modelcard (official model card mirror)
- https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3.5-lightning-30b-a3b (official NIM reference)
- https://developer.nvidia.com/topics/ai/nemotron (official family overview)
- ../providers/kilo-code.md (`nvidia/nemotron-3.5-lightning:free`, 1M context — live catalog 2026-09-05)
- ../providers/openrouter.md (`nvidia/nemotron-3.5-lightning:free` — live roster 2026-09-05)
- ../providers/opencode-zen.md (`nemotron-3.5-lightning-free` — verified working anonymously 2026-09-05)
- ../providers/unorouter.md (`nemotron-3.5-lightning:free` — free catalog 2026-09-05)
