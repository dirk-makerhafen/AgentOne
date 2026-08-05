---
name: mimo-v2.5-pro
family: mimo
series: mimo-v2.5
vision: false
supports_reasoning: true
supports_tool_call: true
open_weights: true
self_hosted: true
total_parameters: 1020.0
active_parameters: 42.0
context_length: 1048576
providers:
  - xiaomi
  - openrouter
  - kenari
  - unorouter
  - aihubmix
---
Xiaomi MiMo-V2.5-Pro is Xiaomi's most capable open-weight model — a 1.02T parameter Mixture-of-Experts model with 42B active parameters, built on a hybrid-attention architecture with a 1M token context window. Released April 2026 under the MIT license.

**Key Capabilities:**
- MoE architecture: 1.02T total / 42B active parameters
- 1M token context window (256K on Base variant)
- Hybrid attention: Sliding Window Attention (SWA) + Global Attention (GA) at 6:1 ratio — ~7× KV-cache reduction
- Multi-Token Prediction (MTP): ~3× output throughput
- Native reasoning/thinking mode
- Full function/tool calling support
- Long-horizon agentic and complex software engineering focus
- Open weights on Hugging Face (`XiaomiMiMo/MiMo-V2.5-Pro`, FP8) and ModelScope
- MIT license (fully permissive)

**Free Access:**
- **Xiaomi**: https://api.xiaomimimo.com/v1 — free tier with `XIAOMI_API_KEY`
- **OpenRouter**: `xiaomi/mimo-v2.5-pro:free` — 200 req/day free tier
- **Kenari**: `xiaomi/mimo-v2.5-pro:free` — free tier
- **UnoRouter**: free tier variant available
- **AIHubMix**: `xiaomi-mimo-v2-5-pro:free` — free tier

**Benchmarks:** LMSYS Elo ~1462.5 — top-3 open-weight model. Significant improvements over MiMo-V2-Pro in general agentic capabilities, complex software engineering, and long-horizon tasks. Rivals closed frontier models on coding and agent benchmarks.

**Self-Hosting:** 1.02T MoE — native FP8 weights need ~600GB+ VRAM (8×H100-80GB minimum, capped at ~256K context; 8×H200 for full 1M). Supported by SGLang (first-class), vLLM.

**License:** MIT (fully permissive, commercial use allowed, no restrictions).

**Note:** Ex-DeepSeek researcher Luo Fuli leads the MiMo team. This is Xiaomi's first open-weight Pro-tier model — a top-tier open-weight flagship for agentic and long-context production use.
