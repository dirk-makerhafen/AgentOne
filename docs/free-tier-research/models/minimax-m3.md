---
name: minimax-m3
family: minimax
series: minimax-m3
vision: true
supports_reasoning: true
supports_tool_call: true
open_weights: true
self_hosted: true
total_parameters: 428.0
active_parameters: 23.0
context_length: 1000000
providers:
  - minimax
  - openrouter
  - ollama-cloud
  - kenari
  - nvidia-nim
  - opencode-zen
---
MiniMax M3 is MiniMax's flagship open-weight model — a ~428B parameter natively multimodal Mixture-of-Experts with ~23B active parameters, a 1M token context window via proprietary MiniMax Sparse Attention (MSA), and frontier coding/agentic performance. Released June 2026.

**Key Capabilities:**
- MoE architecture: ~428B total / ~23B active (128 experts, 4 activated)
- 1M token context window (512K+ guaranteed; MSA sparse attention)
- Native multimodality from step 0: text, image, and video input
- Three reasoning modes via `thinking` param (enabled / adaptive / disabled)
- Full function/tool calling, agentic (can operate a desktop computer)
- MSA: 9× prefill and 15× decode speedups vs M2 at 1M context, 1/20 per-token compute
- Open weights on Hugging Face (`MiniMaxAI/MiniMax-M3`)
- MiniMax Community License

**Free Access:**
- **MiniMax**: https://api.minimax.io — free tier with `MINIMAX_API_KEY`
- **OpenCode Zen**: `minimax-m3` — built-in free for opencode users
- **OpenRouter**: `minimax/minimax-m3:free` — 200 req/day free tier
- **Kenari**: `minimax-m3` — free tier
- **Ollama Cloud / NVIDIA NIM**: free tiers

**Benchmarks:** LMSYS Elo ~1436.7 — top open-weight multimodal model. Frontier coding and long-horizon agentic performance. USAMO 20%+ on MathArena.

**Self-Hosting:** 428B MoE (BF16/MXFP8). Supports 1M context. Supported by vLLM, SGLang, NVIDIA NeMo (SFT/LoRA/RL); deploy on NVIDIA Blackwell.

**License:** MiniMax Community License (open, permissive for commercial use).

**Note:** First and only open-weight model combining frontier coding, million-token context, and native multimodality in one model. M3 is a flagship multimodal/agentic choice.