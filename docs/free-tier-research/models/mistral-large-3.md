---
name: mistral-large-3
family: mistral
series: mistral-large
vision: true
supports_reasoning: false
supports_tool_call: true
open_weights: true
self_hosted: true
total_parameters: 675.0
active_parameters: 41.0
context_length: 262144
providers:
  - mistral
  - openrouter
  - together-ai
  - nvidia-nim
  - ollama-cloud
---
Mistral Large 3 is Mistral AI's flagship open-weight model — a 675B parameter granular Mixture-of-Experts with 41B active parameters (39B LM + 2.5B vision encoder), native multimodal input, 256K context window, and best-in-class agentic function calling. Released December 2025 under the Apache 2.0 license.

**Key Capabilities:**
- Granular MoE architecture: 675B total / 41B active parameters
- 256K token context window
- Native vision (image input) + multilingual (dozens of languages)
- Native function calling and JSON output (best-in-class agentic)
- Strong system prompt adherence
- Open weights on Hugging Face (`mistralai/Mistral-Large-3-675B-Instruct-2512`)
- Apache 2.0 license

**Free Access:**
- **Mistral AI**: https://api.mistral.ai/v1 — free "Experiment" plan (~1B tokens/month, 1 req/sec, no credit card)
- **OpenRouter**: `mistral/mistral-large-3:free` — 200 req/day free tier
- **Together AI**: `mistralai/Mistral-Large-3-675B-Instruct` — free tier, $5 credits
- **NVIDIA NIM**: free prototyping endpoint on build.nvidia.com
- **Ollama Cloud**: `mistral-large-3:675b` — free tier

**Benchmarks:** LMSYS Elo ~1429.8. Best-in-class agentic capabilities with frontier general performance. Strong vision, coding, and multilingual.

**Self-Hosting:** 675B granular MoE — FP8 runs on one 8×H200 node (256K context); NVFP4 on 8×H100/A100. Supported by vLLM (native support, auto tool choice), SGLang, TRT-LLM.

**License:** Apache 2.0 (fully permissive, commercial use allowed).

**Note:** Mistral Large 3 is Mistral's largest, most capable model. A 3rd-generation MoE (memory-optimized vs Mistral Large). Reasoning variant coming soon. Apache 2.0 makes it ideal for enterprise self-hosting.