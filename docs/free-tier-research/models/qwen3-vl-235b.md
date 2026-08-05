---
name: qwen3-vl-235b
family: qwen
series: qwen3-vl
vision: true
supports_reasoning: true
supports_tool_call: true
open_weights: true
self_hosted: true
total_parameters: 235.0
active_parameters: 22.0
context_length: 262144
providers:
  - alibaba
  - openrouter
  - together-ai
  - siliconflow
  - nvidia-nim
  - novita-ai
---
Qwen3-VL-235B-A22B is Alibaba's flagship vision-language model — a 235B parameter Mixture-of-Experts with 22B active parameters, featuring deep multimodal perception, reasoning over images/video, spatial and video dynamics understanding, and 256K native context (expandable to 1M). Released September 2025 under the Apache 2.0 license.

**Key Capabilities:**
- MoE architecture: 235B total / 22B active parameters
- Native 256K context, expandable to 1M via YaRN RoPE scaling
- Deep visual perception & reasoning; handles hours-long video with second-level indexing
- Enhanced spatial and video dynamics comprehension
- Strong agent interaction (GUI/computer vision agentic)
- Open weights on Hugging Face (`Qwen/Qwen3-VL-235B-A22B-Instruct` and `-Thinking`)
- Apache 2.0 license

**Variants:**
- **Qwen3-VL-235B-A22B-Instruct** — general instruct
- **Qwen3-VL-235B-A22B-Thinking** — enhanced reasoning variant

**Free Access:**
- **OpenRouter**: `qwen/qwen3-vl-235b-a22b-instruct:free` — 200 req/day
- **Together AI**: `Qwen/Qwen3-VL-235B-A22B-Instruct` — free tier, $5 credits
- **SiliconFlow / Novita AI / NVIDIA NIM / Kilo**: free tiers
- **Alibaba Model Studio**: hosted Qwen3-VL API

**Benchmarks:** LMSYS Elo ~1421 (Instruct). Most powerful vision-language model in the Qwen series to date. Strong on multimodal, video understanding, and GUI agentic benchmarks.

**Self-Hosting:** 235B MoE — supported by vLLM, SGLang, transformers with flash-attention-2. Image/video processors configurable (max_pixels) for GPU memory management.

**License:** Apache 2.0 (fully permissive, commercial use allowed).

**Note:** The flagship open-weight multimodal model. Use the Thinking variant for reasoning-heavy vision tasks, Instruct for general. Config.json defaults to 256K; use YaRN for 1M context.