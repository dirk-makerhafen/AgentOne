---
name: Kenari
url: "https://kenari.id"
api_base: "https://kenari.id/v1"
setup_instructions: |
  1. Sign up at https://kenari.id (free, no credit card; Indonesian phone/email or Google/GitHub).
  2. Create an API key in the dashboard (or use the free tier without top-up).
  3. Call the OpenAI-compatible endpoint at https://kenari.id/v1 with the key as Bearer token.
  4. Also supports Anthropic format at the same endpoint.
api_key_url: "https://kenari.id"
limits:
  requests:
    minute: 5
    day: 50
---

Kenari is an Indonesian LLM gateway with a unified API (OpenAI + Anthropic formats), automatic fallback across providers, and billing in Indonesian Rupiah. 23 models are free with generous limits after a small top-up.

**Free Tier:**

- **No top-up (Solo Free):** 50 requests/day, 5 RPM. Free models included.
- **After Rp 10,000 top-up (~$0.60):** 1,000 requests/day, 10 RPM. Free models included.
- **Active monthly plan:** No daily limit, 25 RPM. Plans from Rp 49,000/mo (~$3).
- Pay-as-you-go (PAYG) also available; per-model prices at `/v1/models`.

**Free Models (verified 2026-10-27 from opencode fixtures):**

### Anthropic Claude
- `claude-opus-4-8` — 1M context, reasoning, tool calls
- `claude-opus-4-7` — 1M context, reasoning, tool calls
- `claude-sonnet-4-6` — 1M context, reasoning, tool calls

### OpenAI GPT
- `gpt-5-5` — 1.05M context, reasoning, tool calls
- `gpt-5-4-mini` — 400K context, reasoning, tool calls
- `gpt-oss-120b` — 131K context, reasoning, tool calls, open weights
- `gpt-oss-20b` — 131K context, reasoning, tool calls, open weights
- `gpt-image-2` — 272K context, image generation

### DeepSeek
- `deepseek-v4-flash` — 1M context, reasoning, tool calls
- `deepseek-v4-flash:free` — 1M context, reasoning, tool calls
- `deepseek-v4-pro` — 1M context, reasoning, tool calls
- `deepseek-v4-pro:free` — 1M context, reasoning, tool calls

### GLM (Z.ai)
- `glm-5-1` — 200K context, reasoning, tool calls
- `glm-5-2` — 1M context, reasoning, tool calls

### Kimi (Moonshot)
- `kimi-k2-6` — 262K context, reasoning, tool calls
- `kimi-k2-7-code` — 262K context, reasoning, tool calls

### xAI Grok
- `grok-4-3` — 1M context, reasoning, tool calls
- `grok-build-0-1` — 256K context, reasoning, tool calls

### Xiaomi MiMo
- `mimo-v2-5` — 1M context, reasoning, tool calls
- `mimo-v2-5-pro` — 1M context, reasoning, tool calls

### Google Gemma
- `gemma-4-31b-it` — 262K context, reasoning, tool calls

### Qwen
- `qwen3-7-plus` — 1M context, reasoning, tool calls

### MiniMax
- `minimax-m3` — 512K context, reasoning, tool calls

**Limits:**

- Free (no top-up): 50 RPD, 5 RPM
- After Rp 10,000 top-up: 1,000 RPD, 10 RPM
- Active plan: unlimited daily, 25 RPM
- PAYG: per-token pricing in Rupiah per 1M tokens (see `/v1/models`)

**Notes:**

- Indonesian Rupiah billing; top-up via QRIS, bank transfer, e-wallet (no credit card required for free tier).
- OpenAI-compatible: `https://kenari.id/v1`; Anthropic-compatible at same endpoint.
- Automatic fallback across providers (if one slows down, switches within ms).
- Model IDs use simple names (no provider prefix).
- Also offers Studio (images/video/voice), Domains, MCP server, CLI.
- "Start free" - sign up and use free models immediately.

**Sources**

- https://kenari.id (official site)
- https://kenari.id/en/docs (documentation)
- https://kenari.id/v1/models (live model list & pricing)
- https://kenari.id/openapi.json (OpenAPI spec)
- docs/free-tier-research/raw/opencode-models-api/kenari/ (23 free model fixtures, verified 2026-10-27)