---
name: gemma-4-31b
family: gemma
series: gemma-4
vision: false
supports_reasoning: true
supports_tool_call: true
open_weights: true
self_hosted: true
total_parameters: 31.0
active_parameters: 31.0
context_length: 1000000
providers:
  - google-ai-studio
  - openrouter
  - together-ai
  - unorouter
---
Gemma 4 31B (Gemma 4 27B-A4B MoE) is Google's flagship open-weight model in the Gemma 4 family — a 31B parameter Mixture-of-Experts model with 27B total and 4B active parameters, featuring a 1M token context window and strong reasoning capabilities.

**Key Capabilities:**
- MoE architecture: 27B total / 4B active parameters (Gemma 4 27B-A4B-IT)
- 1M token context window
- Native reasoning/thinking mode support
- Full function/tool calling support
- Multilingual (100+ languages)
- Open weights on Hugging Face (`google/gemma-4-27b-a4b-it`, `google/gemma-4-31b-it`)
- Apache 2.0 license

**Variants:**
- **Gemma 4 27B-A4B-IT** — MoE, 27B/4B, 1M context, instruction tuned
- **Gemma 4 31B-IT** — Dense 31B, 1M context, instruction tuned
- **Gemma 4 12B-IT** — Dense 12B, 1M context
- **Gemma 4 4B/2B/9B** — Smaller variants

**Free Access:**
- **Google AI Studio**: `gemma-4-27b-a4b-it` — free tier, 15 RPM, 1M context
- **OpenRouter**: `google/gemma-4-31b-it:free` — 200 req/day
- **Together AI**: `google/gemma-4-31b-it` — free tier, $5 credits
- **UnoRouter**: `gemma-4-31b-it:free` — free tier

**Benchmarks:** Strong on MMLU, GPQA, MATH. Reasoning mode competitive with larger models. 1M context enables long-document reasoning.

**Self-Hosting:** MoE 27B/4B runs on single 24GB GPU (4-bit). Dense 31B needs ~65GB VRAM 4-bit (dual 48GB or 2×3090). Supported by Ollama, llama.cpp, vLLM, LM Studio, Keras/JAX.

**License:** Apache 2.0 (fully permissive, commercial use allowed).

**Note:** Best open model for single-GPU deployment with 1M context. Google AI Studio free tier is generous (no credit card). The 27B-A4B MoE variant is most efficient; 31B dense is stronger but heavier.