---
name: NVIDIA NIM
url: "https://integrate.api.nvidia.com/v1"
self_hosted: false
---
NVIDIA NIM (NVIDIA Inference Microservices) provides optimized, enterprise-grade inference containers for NVIDIA and partner models. The hosted API at build.nvidia.com offers free prototyping endpoints for all models including flagship Nemotron 3 Ultra, with rate limits suitable for development.

**Authentication:** NGC API key (Bearer token). Get key at https://build.nvidia.com (NVIDIA NGC account required, free).

**Free Tier:**
- Free prototyping endpoints for all models on build.nvidia.com
- Rate limits vary by model; suitable for development/testing, not production
- No credit card required for prototyping tier
- Access to full Nemotron 3 family (Nano, Super, Ultra), Llama-Nemotron, and partner models

**Paid Tier:** NVIDIA AI Enterprise subscription for production deployments with SLAs, security patches, and support. Also available via cloud partners (Together AI, AWS, Azure, GCP, etc.).

**Key Features:**
- OpenAI-compatible API (`/chat/completions`, `/models`)
- Optimized TensorRT-LLM / TRT-LLM backends
- Supports reasoning tokens, tool calling, structured output
- 1M context on Nemotron 3 models
- Self-hosted containers available (vLLM, SGLang, TRT-LLM) for air-gapped deployments
- OpenMDW-1.1 license for Nemotron weights (downloadable from Hugging Face)

**Models of Note (Free Prototyping):**
- `nvidia/nemotron-3-ultra-550b-a55b` — 550B MoE (55B active), 1M context, frontier reasoning
- `nvidia/nemotron-3-super-120b-a12b` — 120B MoE (12B active), 1M context, strong reasoning
- `nvidia/nemotron-3-nano-30b-a3b` — 30B MoE (3B active), consumer GPU friendly
- `nvidia/llama-3.1-nemotron-70b-instruct` — 70B dense, 128K context
- `nvidia/llama-3.3-nemotron-super-49b-v1` — 49B, enhanced reasoning

**Notes:** Best path for NVIDIA's own frontier models (Nemotron 3 Ultra/Super). Free tier is prototyping only; production requires NVIDIA AI Enterprise or cloud partner deployment. Weights are open (OpenMDW-1.1) for self-hosting.