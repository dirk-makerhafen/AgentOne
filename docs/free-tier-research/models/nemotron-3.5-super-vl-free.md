---
name: Nemotron 3.5 Super VL Free
developer: NVIDIA
canonical_id: nvidia/nemotron-3.5-super-vl-120b-a12b
leaderboard_id: nemotron-3.5-super-vl-free
leaderboard_rank: 89
family: nemotron
context_window: 1048576
reasoning: true
tool_call: true
temperature: true
modalities:
  input: [text, image]
  output: [text]
open_weights: true
providers:
  - name: OpenCode Zen
    file: opencode-zen
    model_id: nemotron-3.5-super-vl-free
    conditions: "Anonymous free pool; no account, key, or payment; limited-time free (feedback-collection period)"
    verified: "2026-10-28"
  - name: Fireworks AI
    file: fireworks-ai
    model_id: accounts/fireworks/models/nemotron-3-ultra-nvfp4
    conditions: "Paid model; included for reference (Super VL not on Fireworks free tier)"
    verified: "2026-10-28"
---

Nemotron 3.5 Super VL is NVIDIA's vision-language reasoning model in the Nemotron 3.5 family, featuring 120B total parameters with 12B active (MoE). It handles text, image, and video understanding with agentic tool use capabilities.

**Capabilities:**

- Vision-language model: text and image input with text output (video understanding per NVIDIA)
- MoE architecture: 120B total / 12B active parameters
- Reasoning with configurable effort levels (none, minimal, low, medium, high, xhigh)
- Tool/function calling support
- Reasoning content interleaved in output
- Temperature control
- 1M context window (1M input / 131K output)
- Open weights under NVIDIA Open Model License
- Optimized for agentic tasks across enterprise workloads

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [OpenCode Zen](../providers/opencode-zen.md) | `nemotron-3.5-super-vl-free` | Anonymous free pool; no account, key, or payment; limited-time free | No published numbers; free-pool enforced via `FreeUsageLimitError` | 2026-10-28 |

**Notes:**

- Release date: 2026-10-15
- Canonical model: `nvidia/nemotron-3.5-super-vl-120b-a12b`
- Part of Nemotron 3.5 family (distinct from Nemotron 3 Ultra and Nemotron 3.5 Lightning)
- Free on OpenCode Zen via the inference endpoint `https://opencode.ai/inference/openai/v1`
- Data handling: NVIDIA free endpoints are trial-use only; session logging per NVIDIA API Trial Terms — do not submit personal/confidential data

**Sources**

- https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Super-VL (official weights)
- https://opencode.ai/zen/v1/models (live catalog)
- ../providers/opencode-zen.md (verified 2026-10-28)
- https://developer.nvidia.com/topics/ai/nemotron (NVIDIA Nemotron family)