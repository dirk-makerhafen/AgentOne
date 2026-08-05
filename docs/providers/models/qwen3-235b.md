---
name: qwen3-235b
family: qwen
series: qwen3
vision: false
supports_reasoning: true
supports_tool_call: true
open_weights: true
self_hosted: true
total_parameters: 235.0
active_parameters: 22.0
context_length: 131072
providers:
  - openrouter
  - together-ai
  - groq
  - cerebras
---
Qwen3-235B-A22B is Alibaba's flagship Mixture-of-Experts model with 235B total parameters and 22B active parameters. It features a unique dual-mode architecture supporting seamless switching between "thinking" mode for complex reasoning, math, and code tasks, and "non-thinking" mode for general conversational efficiency.

**Key Capabilities:**
- MoE architecture: 235B total / 22B active parameters
- Dual-mode: Thinking (reasoning) ↔ Non-thinking (efficient chat)
- 131K token context window (extends to 262K with YaRN scaling on some deployments)
- Native tool calling and function calling support
- Strong multilingual support (100+ languages/dialects)
- Advanced instruction following and agent capabilities
- Open weights on Hugging Face (`Qwen/Qwen3-235B-A22B`)

**Free Access:**
- **OpenRouter**: `qwen/qwen3-235b-a22b:free` — 200 req/day, 131K context
- **Together AI**: `Qwen/Qwen3-235B-A22B-FP8` — free tier endpoint, $5 credits
- **Groq**: `qwen/qwen3-235b-a22b` — free tier, ultra-fast LPU inference
- **Cerebras**: `Qwen/Qwen3-235B-A22B-2507` — free tier, wafer-scale speed

**Benchmarks:** Strong reasoning (AIME, GPQA, LiveCodeBench). Thinking mode excels at math/coding; non-thinking mode matches GPT-4o on general tasks.

**Self-Hosting:** Weights on Hugging Face. 235B MoE requires ~480GB VRAM for FP8 (or ~120GB for 4-bit quantized). Supported by vLLM, SGLang, Ollama, llama.cpp.

**License:** Apache 2.0 (permissive, commercial use allowed).

**Note:** The "Thinking 2507" variant (July 2025) has enhanced reasoning but may not be free on all providers. Base model supports both modes via prompt formatting.