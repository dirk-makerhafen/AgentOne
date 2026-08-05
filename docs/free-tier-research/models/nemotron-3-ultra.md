---
name: nemotron-3-ultra
family: nemotron
series: nemotron-3
vision: false
supports_reasoning: true
supports_tool_call: true
open_weights: true
self_hosted: true
total_parameters: 550.0
active_parameters: 55.0
context_length: 1000000
providers:
  - openrouter
  - nvidia-nim
  - together-ai
  - unorouter
  - opencode-zen
---
NVIDIA Nemotron 3 Ultra is the flagship of the Nemotron 3 family — a 550B parameter Mixture-of-Experts model with 55B active parameters per forward pass. Built on a hybrid Transformer-Mamba architecture, it delivers frontier-level reasoning and agentic capabilities with a 1M token context window.

**Key Capabilities:**
- Hybrid Transformer-Mamba MoE architecture (550B total / 55B active)
- 1M token context window with strong long-context performance (RULER benchmark)
- Native reasoning mode with chain-of-thought output
- Full function/tool calling support
- Open weights under OpenMDW-1.1 license (downloadable from Hugging Face)
- Optimized for complex agentic workflows, long-context reasoning, high-stakes analytical workloads

**Free Access:**
- **OpenRouter**: `nvidia/nemotron-3-ultra-550b-a55b:free` — 200 req/day
- **NVIDIA NIM**: `nvidia/nemotron-3-ultra-550b-a55b` on build.nvidia.com — free prototyping endpoint
- **Together AI**: `nvidia/Nemotron-3-Ultra-550B-A55B` — $5 free credits, then pay-as-you-go
- **UnoRouter**: `nemotron-3-ultra-550b-a55b:free` — free tier
- **OpenCode Zen**: `nemotron-3-ultra-free` — built-in free for opencode users

**Benchmarks:** On-par with state-of-the-art open LLMs across diverse benchmarks. 60% fewer reasoning tokens vs Nemotron 2 Nano. 91% PinchBench agent-productivity score.

**Self-Hosting:** Weights available on Hugging Face (`nvidia/Nemotron-3-Ultra-550B-A55B`). Requires enterprise hardware (8×H100-80GB minimum for Super; Ultra needs GB200 NVL72 class). Supported by vLLM, SGLang, TRT-LLM, Ollama (quantized).

**License:** OpenMDW-1.1 (permissive, allows commercial use).

**Note:** Use the instruct/post-trained checkpoint, not the base model. Base weights have not undergone instruction tuning or alignment.