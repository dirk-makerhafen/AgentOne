---
name: Together AI
url: "https://api.together.xyz/v1"
self_hosted: false
---
Together AI is a full-stack AI cloud platform offering serverless inference, fine-tuning, and GPU clusters. They provide $5 in free credits on signup (no credit card required) and a free tier for select open-weight models with reduced rate limits.

**Authentication:** API key (Bearer token). Get key at https://api.together.ai/settings/api-keys after email signup.

**Free Tier:**
- $5 free credits on signup (never expire)
- Free model endpoints with reduced rate limits vs. paid Turbo endpoints
- Access to 200+ open-source models: Llama, Qwen, DeepSeek, Mistral, GLM, Nemotron, Gemma, GPT-OSS, etc.
- Rate limits on free endpoints are lower; paid Turbo endpoints offer 2x faster inference

**Paid Tier:** Pay-as-you-go per token. Serverless pricing competitive (e.g., DeepSeek-V3 ~$0.60/M input, $0.90/M output). Dedicated endpoints and GPU clusters available.

**Key Features:**
- OpenAI-compatible API (`/chat/completions`, `/models`, `/embeddings`)
- Supports function calling, JSON mode, structured output, reasoning tokens
- NVIDIA NIM integration (Nemotron, Llama-Nemotron models on optimized NIM)
- Batch API (50% discount)
- Fine-tuning API (LoRA, full fine-tune)
- Dedicated endpoints with auto-scaling

**Models of Note (Free Tier Available):**
- `deepseek-ai/DeepSeek-V3-0324` — 164K context, 671B MoE (37B active), tool calling
- `Qwen/Qwen3-235B-A22B-FP8` — 131K context, reasoning + non-thinking modes
- `nvidia/Nemotron-3-Ultra-550B-A55B` — 1M context, 550B MoE (55B active), reasoning
- `nvidia/Nemotron-3-Super-120B-A12B` — 1M context, 120B MoE (12B active), reasoning
- `meta-llama/Llama-3.3-70B-Instruct` — 131K context
- `meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8` — 1M context, MoE
- `Z.ai/GLM-5.2` — 128K context, MIT license
- `openai/gpt-oss-120b` — 131K context, open-weight

**Notes:** Best for open-weight flagship models with generous free credits. Together AI often gets new open models first (Nemotron, Qwen, DeepSeek, GLM). Free endpoints are slower than Turbo; upgrade for production.