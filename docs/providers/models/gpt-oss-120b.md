---
name: gpt-oss-120b
family: gpt-oss
series: gpt-oss
vision: false
supports_reasoning: false
supports_tool_call: true
open_weights: true
self_hosted: true
total_parameters: 120.0
active_parameters: 120.0
context_length: 131072
providers:
  - openrouter
  - groq
  - together-ai
  - cerebras
---
GPT-OSS-120B is OpenAI's first open-weight model release since GPT-2 — a 120B parameter dense model trained with OpenAI's latest techniques. It features a novel architecture optimized for efficient inference and strong reasoning without explicit chain-of-thought training.

**Key Capabilities:**
- Dense 120B parameter architecture (not MoE)
- 131K token context window
- Native tool calling and function calling support
- Strong reasoning without explicit CoT training
- Open weights on Hugging Face (`openai/gpt-oss-120b`)
- Apache 2.0 license (fully permissive)

**Free Access:**
- **OpenRouter**: `openai/gpt-oss-120b:free` — 200 req/day
- **Groq**: `openai/gpt-oss-120b` — free tier, ultra-fast LPU inference
- **Together AI**: `openai/gpt-oss-120b` — free tier, $5 credits
- **Cerebras**: `openai/gpt-oss-120b` — free tier, wafer-scale speed

**Benchmarks:** Strong on MMLU, GPQA, HumanEval. Reasoning emerges without CoT training. Competitive with Llama 3.3 70B and Nemotron 3 Super on many tasks.

**Self-Hosting:** 120B dense — ~240GB VRAM FP16, ~65GB 4-bit. Requires multi-GPU or high-end consumer (2×48GB or 4×24GB) with quantization. Supported by vLLM, SGLang, Ollama, llama.cpp, LM Studio.

**License:** Apache 2.0 (fully permissive, commercial use allowed).

**Note:** First open model from OpenAI since 2019. No MoE — simpler to deploy than Nemotron/Qwen MoE models. Apache 2.0 is more permissive than Llama's community license. GPT-OSS-20B also available for smaller deployments.