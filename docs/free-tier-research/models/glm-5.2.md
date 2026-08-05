---
name: glm-5.2
family: glm
series: glm-5
vision: false
supports_reasoning: true
supports_tool_call: true
open_weights: true
self_hosted: true
total_parameters: 120.0
active_parameters: 120.0
context_length: 128000
providers:
  - openrouter
  - together-ai
  - zai
  - unorouter
  - kenari
  - opencode-zen
---
GLM-5.2 (Z.ai GLM-5.2-Max) is Z.ai's flagship open-weight model — a dense 120B parameter model with MIT license, featuring strong reasoning capabilities and 128K context. It's the successor to GLM-4 and competes with GPT-4o/Claude 3.5 Sonnet on benchmarks.

**Key Capabilities:**
- Dense 120B parameter architecture
- 128K token context window
- Native reasoning mode with chain-of-thought
- Full function/tool calling support
- Strong bilingual (English/Chinese) capabilities
- Open weights on Hugging Face (`Z.ai/GLM-5.2`, `Z.ai/GLM-5.2-Max`)
- MIT license (fully permissive)

**Free Access:**
- **OpenRouter**: `zai-org/glm-5.2:free` — 200 req/day
- **Together AI**: `Z.ai/GLM-5.2` — free tier, $5 credits
- **Z.ai Platform**: Direct API at https://open.bigmodel.cn — free tier available
- **UnoRouter**: `glm-5.2:free` — free tier
- **Kenari**: `glm-5.2:free` — free tier
- **OpenCode Zen**: `glm-5.2` / `glm-5-free` / `glm-4.7-free` — built-in free for opencode users

**Benchmarks:** LMSYS Elo ~1465 (GLM-5.2-Max). Strong on MMLU, GPQA, LiveCodeBench, Chinese benchmarks (C-Eval, CMMLU). Competitive with GPT-4o on reasoning and coding.

**Self-Hosting:** 120B dense — ~240GB VRAM FP16, ~65GB 4-bit. Requires multi-GPU (2×48GB or 4×24GB) with quantization. Supported by vLLM, SGLang, Ollama, llama.cpp.

**License:** MIT (fully permissive, commercial use allowed).

**Note:** Best fully-permissive (MIT) open model at 120B scale. Z.ai (formerly Zhipu AI) is a leading Chinese AI lab. GLM-5.1 also available (similar capabilities). Strong Chinese language support makes it unique among flagship open models.