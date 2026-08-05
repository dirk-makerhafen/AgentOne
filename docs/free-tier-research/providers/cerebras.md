---
name: Cerebras
url: "https://api.cerebras.ai/v1"
self_hosted: false
---
Cerebras offers ultra-fast inference on wafer-scale CS-3 clusters (WSE-3). Free tier provides access to open-weight models with no credit card required, targeting high-throughput, low-latency workloads.

**Authentication:** API key (Bearer token). Get key at https://cloud.cerebras.ai/ (email signup, no credit card).

**Free Tier:**
- Free access to select open models: Llama 3.3 70B, Llama 4 Scout/Maverick, Qwen3 235B (2507), GPT-OSS-120B
- Rate limits: generous for development (exact limits not publicly documented)
- No credit card required

**Paid Tier:** Pay-as-you-go per token. Competitive pricing for high-volume inference on CS-3 hardware.

**Key Features:**
- OpenAI-compatible API (`/chat/completions`, `/models`)
- Industry-leading tokens/second on large models (1000+ tok/s on 70B)
- Supports tool calling, JSON mode, structured output
- 131K context on most models

**Models of Note (Free):**
- `meta-llama/Llama-3.3-70B-Instruct` — 131K context, ~1000+ tok/s
- `meta-llama/Llama-4-Maverick-17B-128E-Instruct` — 1M context, MoE
- `meta-llama/Llama-4-Scout-17B-16E-Instruct` — 131K context, MoE
- `Qwen/Qwen3-235B-A22B-2507` — 131K context, reasoning
- `openai/gpt-oss-120b` — 131K context

**Notes:** Fastest inference for open-weight models. Smaller model selection than Groq/Together but unmatched speed on 70B+ models. Good for latency-sensitive applications.