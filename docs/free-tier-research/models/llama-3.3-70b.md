---
name: llama-3.3-70b
family: llama
series: llama-3.3
vision: false
supports_reasoning: false
supports_tool_call: true
open_weights: true
self_hosted: true
total_parameters: 70.0
active_parameters: 70.0
context_length: 131072
providers:
  - openrouter
  - groq
  - together-ai
  - cerebras
  - github-models
---
Llama 3.3 70B is Meta's latest dense 70B parameter model (December 2024), incorporating Grouped-Query Attention (GQA) for enhanced inference efficiency. It matches or exceeds Llama 3.1 405B on many benchmarks at 1/6 the parameter count.

**Key Capabilities:**
- Dense 70B parameter architecture (not MoE)
- Grouped-Query Attention (GQA) for inference scalability
- 131K token context window
- Native tool calling support (Llama-3.3-70B-Instruct)
- Strong multilingual, coding, and reasoning capabilities
- Open weights on Hugging Face (`meta-llama/Llama-3.3-70B-Instruct`)

**Free Access:**
- **OpenRouter**: `meta-llama/llama-3.3-70b-instruct:free` — 200 req/day
- **Groq**: `meta-llama/llama-3.3-70b-versatile` — free tier, ~275 tok/sec on LPU
- **Together AI**: `meta-llama/Llama-3.3-70B-Instruct` — free tier, $5 credits
- **Cerebras**: `meta-llama/Llama-3.3-70B-Instruct` — free tier, ~1000+ tok/sec
- **GitHub Models**: `meta-llama-3.3-70b-instruct` — free (GitHub PAT, retiring June 2026)

**Benchmarks:** MMLU ~86%, HumanEval ~81%, MATH ~68%. Outperforms Llama 3.1 70B and approaches 405B on many tasks.

**Self-Hosting:** 70B dense model — ~140GB VRAM FP16, ~40GB 4-bit quantized. Runs on dual 48GB GPUs or high-end consumer hardware (2×3090/4090) with quantization. Supported by Ollama, llama.cpp, vLLM, LM Studio.

**License:** Llama 3.3 Community License (permissive with commercial restrictions for >700M MAU).

**Note:** Best open-weight dense model for self-hosting. Groq and Cerebras offer exceptional inference speed. GitHub Models access is being retired (existing users only after June 2026).