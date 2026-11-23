---
name: Nemotron 3.5 Lightning Free
developer: NVIDIA
canonical_id: nvidia/nemotron-3.5-lightning
leaderboard_id: nemotron-3.5-lightning-free
leaderboard_rank: 227
family: nemotron
context_window: 1048576
reasoning: true
tool_call: true
temperature: true
modalities:
  input:
  - text
  output:
  - text
open_weights: true
---

Nemotron 3.5 Lightning is NVIDIA's efficiency-tuned 3.5-generation model: a hybrid MoE (30B total / 3B active) combining Mamba-2, MoE, and Attention with Multi-Token Prediction, pre-trained on 20T+ tokens for agents, chatbots, RAG, and instruction following. It is a distinct 3.5-generation model — not the Nemotron 3 Nano despite the matching 30B/3B shape.

**Capabilities:**

- Reasoning trace with configurable on/off via chat template (`enable_thinking=True/False`)
- Tool/function calling (official training includes tool calling; serve recipes use `qwen3_coder` tool-call parser with `--enable-auto-tool-choice`)
- Structured output support
- Temperature control (recommended: temperature 1.0, top_p 0.95)
- Text in / text out
- Up to 1M context window (official: validated at 1M on GB200/B200/8xH100; ~256K memory-bound on single H100 BF16)
- Open weights (BF16 reference weights plus NVFP4, DFlash, and DSpark checkpoints on Hugging Face) under OpenMDW License Agreement v1.1
- Pre-trained on 20T+ tokens
- Knowledge cutoff: 2025-09 (pre-training); post-training May 2026

**Notes:**

- Release date: 2026-08-11
- Canonical model: `nvidia/nemotron-3.5-lightning`
- Distinct from Nemotron 3 Nano (30B/3B shape but different architecture generation)
- Free on OpenCode Zen via the inference endpoint `https://opencode.ai/inference/openai/v1`
- Data handling: NVIDIA free endpoints are trial-use only with session logging under NVIDIA API Trial Terms — do not submit personal or confidential data on free routes

**Sources**

- https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16 (official weights)
- https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b/modelcard (official model card)
- https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3.5-lightning-30b-a3b (NIM reference)
- https://developer.nvidia.com/topics/ai/nemotron (family overview)
- ../providers/opencode-zen.md (verified 2026-10-28)
- ../providers/openrouter.md (roster 2026-10-28)
- ../providers/kilo-code.md (catalog 2026-10-28)
- ../providers/unorouter.md (free catalog 2026-10-28)
