---
name: OpenRouter
url: "https://openrouter.ai/api/v1"
self_hosted: false
---
OpenRouter is a unified LLM API gateway that aggregates 300+ models from all major providers (OpenAI, Anthropic, Google, Meta, Mistral, NVIDIA, DeepSeek, Z.ai, etc.) and open-source model hosts. It offers a generous free tier with access to many flagship models via the `:free` model suffix (e.g., `nvidia/nemotron-3-ultra-550b-a55b:free`, `qwen/qwen3-235b-a22b:free`, `deepseek/deepseek-chat-v3-0324:free`).

**Authentication:** API key (Bearer token). Get key at https://openrouter.ai/keys after email signup.

**Free Tier:**
- 200 requests/day per free model
- Access to 50+ free models including Nemotron 3 Ultra, Qwen3-235B, DeepSeek V3, GLM-5.2, Gemma 4, GPT-OSS-120B, Kimi K2
- Rate limits: ~20 req/min on free models
- No credit card required

**Paid Tier:** Pay-as-you-go per token with automatic routing to cheapest/fastest provider. Credits never expire ($5 minimum).

**Key Features:**
- OpenAI-compatible API (`/chat/completions`, `/models`)
- Automatic failover across providers
- Prompt caching discounts (35-90% off)
- Model routing modes: Balanced, Nitro (fastest), Exacto (fixed provider)
- Supports reasoning tokens, tool calling, structured output, vision

**Notes:** Best single endpoint for accessing diverse flagship models free. Free model availability rotates; check https://openrouter.ai/collections/free-models for current list.