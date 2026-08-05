---
name: UnoRouter
url: "https://api.unorouter.com/v1"
self_hosted: false
---
UnoRouter is an AI model router/aggregator providing OpenAI-compatible API access to a wide range of models including many free variants of flagship models (GPT-5 series, DeepSeek V4, GLM, Nemotron, Gemma, Kimi, etc.).

**Authentication:** API key (Bearer token). Get key at https://unorouter.com (email signup, no credit card).

**Free Tier:**
- Extensive free model catalog with `:free` suffix (20+ models)
- Includes: `gpt-5.5:free`, `gpt-5.4:free`, `gpt-5.2:free`, `deepseek-v4-flash:free`, `deepseek-v4-pro:free`, `nemotron-3-ultra-550b-a55b:free`, `glm-5.2:free`, `glm-4.5-flash:free`, `gemma-4-31b-it:free`, `qwen3.5-397b-a17b:free`, `minimax-m2.7:free`, `step-3.7-flash:free`, `kimi-k2.6:free`
- Rate limits apply (not publicly documented)
- No credit card required

**Paid Tier:** Pay-as-you-go per token for non-free models.

**Key Features:**
- OpenAI-compatible API (`/chat/completions`, `/models`)
- Aggregates models from multiple upstream providers
- One of the broadest free model selections among aggregators
- Offers free access to very recent models (GPT-5 series, Nemotron 3 Ultra, DeepSeek V4)
- Supports reasoning, tool calling, structured output, vision

**Models of Note (Free):**
- `gpt-5.5:free` / `gpt-5.4:free` / `gpt-5.2:free` — Latest GPT-5 series
- `nemotron-3-ultra-550b-a55b:free` — 1M context, frontier reasoning
- `deepseek-v4-flash:free` / `deepseek-v4-pro:free` — 1M context, reasoning
- `glm-5.2:free` — 128K context, MIT license
- `gemma-4-31b-it:free` — 1M context, MoE
- `qwen3.5-397b-a17b:free` — Large MoE
- `kimi-k2.6:free` — 128K context, MoE

**Notes:** UnoRouter has one of the most aggressive free tier offerings, often getting new flagship models as free variants quickly. Less known than OpenRouter but worth checking for free access to latest models. Rate limits and stability may vary.