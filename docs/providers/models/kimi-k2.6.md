---
name: kimi-k2.6
family: kimi
series: kimi-k2
vision: false
supports_reasoning: true
supports_tool_call: true
open_weights: true
self_hosted: true
total_parameters: 1000.0
active_parameters: 1000.0
context_length: 128000
providers:
  - openrouter
  - moonshot
  - together-ai
  - unorouter
  - kenari
  - opencode-zen
---
Kimi K2.6 is Moonshot AI's flagship model — a 1 trillion parameter MoE model (exact active params undisclosed) with Modified MIT license. It features strong reasoning capabilities and 128K context, ranking among the top open-weight models on LMSYS Arena.

**Key Capabilities:**
- MoE architecture: ~1T total parameters (active params not publicly disclosed)
- 128K token context window
- Native reasoning/thinking mode
- Full function/tool calling support
- Strong bilingual (English/Chinese) capabilities
- Open weights on Hugging Face (`moonshotai/Kimi-K2.6`, `moonshotai/Kimi-K2.5-Thinking`)
- Modified MIT license (permissive with attribution)

**Variants:**
- **Kimi K2.6** — Base flagship, strong general capabilities
- **Kimi K2.5-Thinking** — Enhanced reasoning variant
- **Kimi K2.7-Code** — Coding-specialized variant

**Free Access:**
- **OpenRouter**: `moonshotai/kimi-k2.6:free` — 200 req/day
- **Together AI**: `moonshotai/Kimi-K2.6` — free tier, $5 credits
- **Moonshot Platform**: https://platform.moonshot.ai — free tier with email signup
- **UnoRouter**: `kimi-k2.6:free` — free tier
- **Kenari**: `kimi-k2-6` — free tier
- **OpenCode Zen**: `kimi-k2.6` / `kimi-k2.5-free` / `kimi-k2.7-code` — built-in free for opencode users

**Benchmarks:** LMSYS Elo ~1455 (K2.6), ~1445 (K2.5-Thinking). Top-tier open-weight performance. Strong on AIME, GPQA, LiveCodeBench, Chinese benchmarks.

**Self-Hosting:** 1T MoE — exact hardware requirements not public. Likely requires significant multi-GPU infrastructure. Quantized versions may run on smaller setups. Supported by vLLM, SGLang.

**License:** Modified MIT (permissive with attribution requirement).

**Note:** Moonshot AI (Kimi) is a leading Chinese AI lab. Kimi models are known for exceptional long-context and Chinese language capabilities. The Modified MIT license requires attribution but allows commercial use.