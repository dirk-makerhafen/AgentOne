---
name: Kenari
url: "https://kenari.id/v1"
self_hosted: false
---
Kenari is an Indonesian AI model router/aggregator providing OpenAI-compatible API access to a wide range of models including free variants of flagship models. It offers a generous free tier with no credit card required.

**Authentication:** API key (Bearer token). Get key at https://kenari.id (email signup, no credit card).

**Free Tier:**
- Free access to select models with `:free` suffix (e.g., `deepseek-v4-flash:free`, `deepseek-v4-pro:free`, `glm-5.2:free`, `gpt-oss-120b`, `gpt-5.4-mini`, `kimi-k2-6`, `gemma-4-31b-it`)
- Rate limits apply (not publicly documented)
- No credit card required

**Paid Tier:** Pay-as-you-go per token for non-free models.

**Key Features:**
- OpenAI-compatible API (`/chat/completions`, `/models`)
- Aggregates models from multiple providers
- Offers free variants of recent flagship models (DeepSeek V4, GLM-5.2, GPT-5 series, Kimi K2, Gemma 4)
- Supports reasoning, tool calling, structured output, vision

**Models of Note (Free):**
- `deepseek-v4-flash:free` — 1M context, reasoning, tool calling
- `deepseek-v4-pro:free` — 1M context, reasoning, tool calling
- `glm-5.2:free` — 128K context, MIT license
- `gpt-oss-120b` — 131K context, Apache 2.0
- `kimi-k2-6` — 128K context, MoE
- `gemma-4-31b-it` — 1M context, MoE

**Notes:** Kenari is a lesser-known but capable aggregator with strong free model offerings. Good alternative to OpenRouter for accessing free variants of latest models. Based in Indonesia; consider latency for non-APAC users.