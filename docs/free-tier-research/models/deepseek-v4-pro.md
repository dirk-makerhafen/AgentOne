---
name: deepseek-v4-pro
family: deepseek
series: deepseek-v4
vision: false
supports_reasoning: true
supports_tool_call: true
open_weights: true
self_hosted: true
total_parameters: 1600.0
active_parameters: 49.0
context_length: 1000000
providers:
  - openrouter
  - together-ai
  - deepseek
  - kenari
  - unorouter
  - nvidia-nim
  - siliconflow
---
DeepSeek V4 Pro is the flagship of the DeepSeek V4 series — a 1.6T parameter Mixture-of-Experts model with 49B active parameters, supporting a one-million-token context window. Released April 2026 as the frontier tier of the V4 preview family under the MIT license.

**Key Capabilities:**
- MoE architecture: 1.6T total / 49B active parameters
- 1M token context window (Think Max mode recommends ≥384K)
- Hybrid attention: Compressed Sparse Attention (CSA) + Heavily Compressed Attention (HCA)
- Only 27% of single-token FLOPs and 10% of KV cache vs DeepSeek-V3.2 at 1M context
- Native reasoning with three effort modes (including Think Max)
- Full function/tool calling support
- Manifold-Constrained Hyper-Connections (mHC) for stability
- Open weights on Hugging Face (`deepseek-ai/DeepSeek-V4-Pro`, FP4+FP8 mixed)
- MIT license

**Free Access:**
- **Kenari**: `deepseek-v4-pro:free` — free tier
- **UnoRouter**: `deepseek-v4-pro:free` / `deepseek-v4-pro-high-preview:free` — free tier
- **OpenRouter**: `deepseek/deepseek-v4-pro:free` — 200 req/day (check free collection)
- **Together AI**: `deepseek-ai/DeepSeek-V4-Pro` — free tier, $5 credits
- **NVIDIA NIM**: free prototyping endpoint on build.nvidia.com
- **SiliconFlow / DeepSeek Platform**: free credits on signup

**Benchmarks:** LMSYS Elo ~1450.9 — top open-weight model. SWE-Bench Verified 80.6%. Frontier-level coding, strong reasoning and long-context. Trained on 33T tokens.

**Self-Hosting:** 1.6T MoE — ~865GB on disk (FP4+FP8). Requires enterprise multi-GPU infrastructure (8×H200 or larger). Supported by vLLM, SGLang, TRT-LLM.

**License:** MIT (fully permissive, commercial use allowed).

**Note:** V4-Flash (284B/13B) is the efficient sibling. V4-Pro is the frontier flagship. The V4 series redefines million-token context efficiency — significantly cheaper long-context inference than V3.
