---
name: qwen3.5-397b-a17b
family: qwen
series: qwen3.5
vision: true
supports_reasoning: true
supports_tool_call: true
open_weights: true
self_hosted: true
total_parameters: 397.0
active_parameters: 17.0
context_length: 262144
providers:
  - alibaba
  - openrouter
  - together-ai
  - siliconflow
  - unorouter
  - nvidia-nim
---
Qwen3.5-397B-A17B is Alibaba's flagship open-weight model — a 397B parameter hybrid Mixture-of-Experts with 17B active parameters, featuring native vision/multimodal input, strong reasoning, and 262K native context (extensible to 1M). Released February 2026 under the Apache 2.0 license.

**Key Capabilities:**
- Hybrid MoE architecture: 397B total / 17B active (Gated DeltaNet + MoE, 512 experts, 10 routed + 1 shared)
- 262K native context, extensible to 1,010,000 tokens via YaRN RoPE scaling
- Native multimodal: text, image, video input (ViT vision encoder)
- Thinking mode by default (reasoning), can be disabled
- Full function/tool calling, agentic workflows (Qwen-Agent, MCP)
- Open weights on Hugging Face (`Qwen/Qwen3.5-397B-A17B`) and ModelScope
- Apache 2.0 license

**Free Access:**
- **OpenRouter**: `qwen/qwen3.5-397b-a17b:free` — 200 req/day
- **UnoRouter**: `qwen3-5-397b-a17b:free` — free tier
- **Together AI**: `Qwen/Qwen3.5-397B-A17B` — free tier, $5 credits
- **SiliconFlow / NVIDIA NIM / DeepInfra / Nebius**: free tiers
- **Alibaba Model Studio**: `qwen3.5-397b-a17b` via Qwen3.5-Plus hosted API (1M context)

**Benchmarks:** LMSYS Elo ~1438. Frontier-level coding, math, and agentic benchmarks. Strong multimodal understanding.

**Self-Hosting:** 397B MoE — recommended 8×B200/H200 with TP=8, 262K context. Supported by vLLM, SGLang. Use Qwen3.5-Plus for managed 1M-context hosting.

**License:** Apache 2.0 (fully permissive, commercial use allowed).

**Note:** The successor to Qwen3-235B (the older curated flagship). First release of the Qwen3.5 generation. Qwen3.5-Plus is the hosted 1M-context version. Best-in-class open multimodal flagship.