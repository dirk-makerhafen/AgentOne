---
name: Nemotron 3 Nano 30B A3B
developer: Nvidia
canonical_id: nvidia/nemotron-3-nano-30b-a3b
leaderboard_id: nemotron-3-nano-30b-a3b
leaderboard_rank: 219
family: nemotron
context_window: 131072
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

Nemotron 3 Nano 30B A3B is Nvidia's small MoE for efficient coding, math, and long-context agents (fixture-reported facts; verify live).

**Capabilities:**

- Reasoning, tool/function calling, temperature control (fixture-reported).
- Text in / text out; ~131K context (fixture-reported).
- Open weights.

**Notes:**

- Sibling `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` is also free on Requesty; larger Nemotron 3 siblings (Super 120B, Ultra 550B) have their own free rows there — split into separate cards if their availability diverges.
- Omni exclusion (verified 2026-09-05): the Kilo Code (`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`) and OpenRouter (same ID) free lanes were NOT added here because official NVIDIA docs confirm Omni is a distinct model, not a Nano variant — it is a multimodal (video/audio/image/text) perception sub-agent with its own model page, Hugging Face repo (`nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16`), and technical report (see Sources). It deserves its own card if cataloged.

**Sources**

- raw/opencode-models-api/nvidia/model_nemotron-3-nano-30b-a3b.json (capabilities/context — discovery data)
- https://docs.requesty.ai/features/free-models
- https://fastrouter.ai/models?order=newest
- ../providers/aihubmix.md (`nemotron-3-nano-30b-a3b-free`, 256K context, 100/day · 10/min topped-up — free page verified 2026-09-05)
- https://developer.nvidia.com/topics/ai/nemotron (official: Nano Omni 30B A3B is a separate multimodal video/audio/image/text model vs Nano 30B A3B for coding/reasoning/math — Omni exclusion evidence)
- https://build.nvidia.com/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning (official: Omni has its own NIM page — Omni exclusion evidence)
