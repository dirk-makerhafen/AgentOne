---
name: nemotron-3-super
family: nemotron
series: nemotron-3
vision: false
supports_reasoning: true
supports_tool_call: true
open_weights: true
self_hosted: true
total_parameters: 120.0
active_parameters: 12.0
context_length: 1000000
providers:
  - openrouter
  - nvidia-nim
  - together-ai
  - opencode-zen
---
NVIDIA Nemotron 3 Super is the mid-size model in the Nemotron 3 family — a 120B parameter Mixture-of-Experts model with 12B active parameters. It shares the same hybrid Transformer-Mamba MoE architecture as Ultra but runs on consumer-grade hardware (8×H100-80GB minimum).

**Key Capabilities:**
- Hybrid Transformer-Mamba MoE: 120B total / 12B active parameters
- 1M token context window
- Native reasoning mode with chain-of-thought
- Full function/tool calling support
- Open weights under OpenMDW-1.1 license
- Optimized for reasoning, coding, and agentic tasks

**Free Access:**
- **OpenRouter**: `nvidia/nemotron-3-super-120b-a12b:free` — 200 req/day, 1M context
- **NVIDIA NIM**: `nvidia/nemotron-3-super-120b-a12b` on build.nvidia.com — free prototyping
- **Together AI**: `nvidia/Nemotron-3-Super-120B-A12B` — free tier, $5 credits
- **OpenCode Zen**: `nemotron-3-super-free` — built-in free for opencode users

**Benchmarks:** Strong reasoning (AIME, GPQA, MATH). 91% PinchBench agent score (same architecture as Ultra). Outperforms most open models at its compute class.

**Self-Hosting:** Weights on Hugging Face (`nvidia/Nemotron-3-Super-120B-A12B`). Minimum 8×H100-80GB for FP8. Quantized versions run on fewer GPUs. Supported by vLLM, SGLang, TRT-LLM, Ollama.

**License:** OpenMDW-1.1 (permissive, commercial use allowed).

**Note:** Best balance of capability and hardware requirements in Nemotron 3 family. The "Thinking" variant (`nvidia/nemotron-3-super-120b-a12b-thinking`) has enhanced reasoning. Use instruct checkpoint, not base.