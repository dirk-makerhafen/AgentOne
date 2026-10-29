---
name: Cortecs
url: "https://cortecs.ai"
api_base: "https://api.cortecs.ai/v1"
setup_instructions: |
  1. Sign up at https://cortecs.ai (European company, GDPR-compliant).
  2. Create an API key in the dashboard.
  3. Call the OpenAI-compatible endpoint at https://api.cortecs.ai/v1 with the key as Bearer token.
  4. Also supports Anthropic format at the same endpoint.
api_key_url: "https://cortecs.ai"
limits:
  requests:
    minute: 60
    day: 1000
---

Cortecs is a European LLM router (GDPR-native, ISO certified) with 150+ models via 16 EU-based providers. 4 models are free; paid models charged at upstream rates + 5% service fee.

**Free Tier:**

- No separate free tier — free models available to all users.
- 4 models free: Llama 3.1 405B, GPT-OSS 120B, Devstral 2512, Devstral Small 2512.
- Platform-wide limits apply; no additional rate limits documented for free models.
- 5% service fee on balance top-ups; token pricing at upstream provider rates (EUR).

**Free Models (verified 2026-10-27 from opencode fixtures):**

- `llama-3.1-405b-instruct` — 128K context, tool calls
- `gpt-oss-120b` — 128K context, tool calls, open weights
- `devstral-2512` — 262K context, tool calls
- `devstral-small-2512` — 262K context, tool calls

**Paid Models (53 models, representative, verified 2026-10-27):**

- `claude-sonnet-4` — 200K context, €3.31/€16.54 per 1M
- `claude-opus-4-6` — 1M context, €5.98/€29.89 per 1M
- `deepseek-v4-flash` — 1M context, €0.13/€0.27 per 1M
- `deepseek-v4-pro` — 1M context, €1.55/€3.11 per 1M
- `gpt-4.1` — 1M context, €2.35/€9.42 per 1M
- `gpt-5.4` — 1M context, €3.00/€16.13 per 1M
- `kimi-k2-thinking` — 262K context, €0.66/€2.73 per 1M
- `minimax-m3` — 512K context, €0.36/€1.78 per 1M
- `qwen3-coder-480b-a35b` — 262K context, €0.44/€1.98 per 1M
- `glm-5` — 203K context, €1.08/€3.44 per 1M
- `gemini-2.5-pro` — 1M context, €1.65/€11.02 per 1M
- +42 more models (Claude, DeepSeek, GLM, Kimi, MiniMax, Qwen, Nemotron, Mistral, Codestral, Hermes, Nova, Mixtral, Llama)

**Limits:**

- "No rate limits" on platform level (unrestricted access to platform-wide limits).
- May manage traffic during maintenance or DDoS protection.
- 5% service fee on top-ups; pay upstream provider rates per 1M tokens.
- Free models: $0 input/output.

**Notes:**

- GDPR-native: acts as primary Data Processor, manages compliance for upstream providers.
- EU sovereignty option: route exclusively through EU-established providers (16 active: Arkane, Berget, Entrim, Inceptron, Infercom, Ionos, Mistral, Nebius, OVH, Scaleway, TensorX, etc.).
- OpenAI + Anthropic compatible endpoint: `https://api.cortecs.ai/v1`.
- Automatic filter-and-rank routing (price + performance).
- 5% service fee on top-ups; no markup on token prices.
- No data storage/training on user prompts; payload deleted after request.
- Integrations: OpenCode, GitHub Copilot, LibreChat, Langfuse, LangChain, Vercel AI SDK, LlamaIndex, n8n, Make.com, Pydantic AI, Cline, Zed, LobeChat, etc.
- Based in Vienna, Austria (Cortecs GmbH).

**Sources**

- https://cortecs.ai (official site)
- https://cortecs.ai/docs (documentation)
- https://api.cortecs.ai/v1/models (live model list & pricing)
- https://cortecs.ai/openapi.json (OpenAPI spec)
- docs/free-tier-research/raw/opencode-models-api/cortecs/ (57 model fixtures, 4 free, verified 2026-10-27)