---
name: deepseek-v3
family: deepseek
series: deepseek-v3
vision: false
supports_reasoning: false
supports_tool_call: true
open_weights: true
self_hosted: true
total_parameters: 671.0
active_parameters: 37.0
context_length: 164000
providers:
  - openrouter
  - together-ai
  - deepseek
  - kenari
  - unorouter
---
DeepSeek-V3 (specifically V3-0324 / V3.1) is a 671B parameter Mixture-of-Experts model with 37B active parameters, rivaling leading closed-source models on benchmarks while being fully open-weight. The V3.1 update (August 2025) added hybrid thinking/non-thinking modes.

**Key Capabilities:**
- MoE architecture: 671B total / 37B active parameters
- 164K token context window (128K on V3.1)
- Native function/tool calling support (V3/V3.1)
- V3.1: Hybrid thinking ↔ non-thinking modes for reasoning vs speed
- Strong coding (LiveCodeBench 56.4% pass@1 non-thinking, 74.8% thinking)
- Strong math (AIME 2024 66.3% non-thinking, 93.1% thinking)
- MMLU-Redux 91.8% (non-thinking), 93.7% (thinking)
- Open weights on Hugging Face (`deepseek-ai/DeepSeek-V3-0324`, `deepseek-ai/DeepSeek-V3.1`)

**Free Access:**
- **OpenRouter**: `deepseek/deepseek-chat-v3-0324:free` — 200 req/day, 164K context
- **Together AI**: `deepseek-ai/DeepSeek-V3-0324` — free tier endpoint, $5 credits
- **DeepSeek Platform**: `deepseek-chat` — $5 free credits on signup
- **Kenari**: `deepseek-v4-flash:free` — free tier (note: V4 Flash, not V3)
- **UnoRouter**: `deepseek-v4-flash:free` / `deepseek-v4-pro:free` — free tier (V4 series)

**Benchmarks:** Outperforms most open models; rivals GPT-4o/Claude 3.5 Sonnet on coding and reasoning. V3.1 thinking mode reaches 93.1% on AIME 2024.

**Self-Hosting:** 671B MoE requires ~1.3TB VRAM for FP8 (~350GB for 4-bit). Supported by vLLM, SGLang, TRT-LLM. Quantized versions available for smaller hardware.

**License:** MIT (permissive, commercial use allowed).

**Note:** DeepSeek-R1 is the reasoning-specialized variant (671B MoE, chain-of-thought). V3/V3.1 are general-purpose with optional thinking mode. V3.1 is the latest and recommended version.