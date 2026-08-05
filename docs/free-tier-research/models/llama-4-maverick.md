---
name: llama-4-maverick
family: llama
series: llama-4
vision: true
supports_reasoning: false
supports_tool_call: true
open_weights: true
self_hosted: true
total_parameters: 400.0
active_parameters: 17.0
context_length: 1000000
providers:
  - openrouter
  - together-ai
  - cerebras
  - groq
  - github-models
---
Llama 4 Maverick is Meta's flagship Mixture-of-Experts model (April 2025) — 400B total parameters with 17B active across 128 experts. It features native multimodal support (vision) and a 1M token context window, making it the most capable open-weight Llama model to date.

**Key Capabilities:**
- MoE architecture: 400B total / 17B active (128 experts)
- Native multimodal: text + vision input
- 1M token context window
- Full function/tool calling support
- Strong multilingual (200+ languages)
- Open weights on Hugging Face (`meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8`)
- Apache 2.0 license (with Llama 4 acceptable use policy)

**Free Access:**
- **OpenRouter**: `meta-llama/llama-4-maverick-17b-128e-instruct:free` — 200 req/day
- **Together AI**: `meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8` — free tier, $5 credits
- **Cerebras**: `meta-llama/Llama-4-Maverick-17B-128E-Instruct` — free tier, wafer-scale speed
- **Groq**: `meta-llama/llama-4-maverick-17b-128e-instruct` — free tier, LPU speed
- **GitHub Models**: `meta-llama-4-maverick-17b-128e-instruct` — free (existing users only)

**Benchmarks:** Strong on MMLU, GPQA, MATH, multimodal benchmarks. 1M context enables full-repo coding and long-document analysis. Outperforms Llama 3.1 405B on most tasks at 1/10 active params.

**Self-Hosting:** 400B MoE (17B active) — ~80GB VRAM FP8 for active params, ~300GB for full. Quantized (4-bit) runs on 4×48GB or 8×24GB. Supported by vLLM, SGLang, Ollama, llama.cpp.

**License:** Llama 4 Community License (Apache 2.0 base with acceptable use restrictions).

**Note:** Best open multimodal model with 1M context. Llama 4 Scout (17B active, 16 experts, 131K context) is the smaller variant. Maverick is the flagship. Apache 2.0 base license is permissive; check Llama 4 acceptable use policy for commercial deployment.