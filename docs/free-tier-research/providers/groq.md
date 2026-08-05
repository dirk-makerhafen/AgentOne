---
name: Groq
url: "https://api.groq.com/openai/v1"
self_hosted: false
---
Groq provides ultra-fast LLM inference on custom LPU (Language Processing Unit) hardware. All models on the platform are available on the free tier with no credit card required — the only limits are rate limits.

**Authentication:** API key (Bearer token). Get key at https://console.groq.com/keys (no credit card, email only).

**Free Tier:**
- ~30 requests/minute, ~14,400 requests/day (organization-level limits)
- Token limits per model (e.g., ~12K tokens/min on Llama 3.3 70B)
- All models available free: Llama 3.3 70B, Llama 4 Scout/Maverick, Qwen3 32B, GPT-OSS-120B/20B, Gemma 7B/27B, DeepSeek R1 Distill, Whisper
- No credits system — purely rate-limited

**Paid Tier (Developer):** ~10x rate limits + 25% discount, no minimum spend. Requires credit card.

**Key Features:**
- OpenAI-compatible API (`/chat/completions`, `/models`)
- Sub-second latency on 70B+ models
- Supports tool calling (Llama-3-Groq-70B-Tool-Use), JSON mode, structured output
- No vision support currently

**Models of Note (Free):**
- `meta-llama/llama-3.3-70b-versatile` — 131K context, best general-purpose 70B
- `meta-llama/llama-4-scout-17b-16e-instruct` — 131K context, MoE
- `openai/gpt-oss-120b` — 131K context, open-weight
- `qwen/qwen3-32b` — 131K context, reasoning capable
- `deepseek-r1-distill-llama-70b` — reasoning model

**Notes:** Fastest free inference for open-weight models. Rate limits are generous enough for prototyping and light production. No proprietary models (no GPT-4o, Claude, Gemini).