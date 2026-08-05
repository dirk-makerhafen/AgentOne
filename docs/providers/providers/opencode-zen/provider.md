---
name: OpenCode Zen
url: "https://opencode.ai/zen/v1"
self_hosted: false
---
OpenCode Zen is the built-in model provider for the opencode AI coding agent. It provides free access to 79+ models including many flagship models at zero cost, with no separate API key required — it uses your opencode authentication.

**Authentication:** Uses your existing opencode session (via `OPENCODE_API_KEY` or `OPENCODE_ZEN_API_KEY`). No separate signup needed.

**Free Tier:**
- All 79 models available free within opencode
- Includes flagship models with `-free` suffix: `deepseek-v4-flash-free`, `nemotron-3-ultra-free`, `glm-4.7-free`, `glm-5-free`, `glm-5.2`, `kimi-k2.5-free`, `minimax-m3-free`, `mimo-v2.5-free`, `nemotron-3-super-free`, `qwen3.6-plus-free`, `ring-2.6-1t-free`
- Also includes non-free variants of: `deepseek-v4-flash`, `deepseek-v4-pro`, `kimi-k2`, `kimi-k2.6`, `glm-5.1`, `glm-5.2`, `gemini-3-flash`, `gemini-3-pro`, `gpt-5`, `gpt-5.4`, `claude-sonnet-4`, `claude-opus-4.5`, etc.
- Rate limits managed by opencode service

**Key Features:**
- Built into opencode — zero configuration
- OpenAI-compatible API at `https://opencode.ai/zen/v1`
- 79 models including latest GPT-5, Claude Opus 4.x, Gemini 3, Nemotron 3 Ultra, GLM-5, DeepSeek V4, Kimi K2
- Supports reasoning, tool calling, structured output, vision
- Automatic model routing within opencode

**Models of Note (Free):**
- `deepseek-v4-flash-free` — 1M context, reasoning, tool calling
- `nemotron-3-ultra-free` — 1M context, frontier reasoning (550B MoE)
- `glm-5-free` / `glm-5.2` — 128K context, MIT license
- `nemotron-3-super-free` — 1M context, reasoning (120B MoE)
- `kimi-k2.5-free` — 128K context, MoE
- `minimax-m3-free` — 1M context
- `qwen3.6-plus-free` — 131K context
- `ring-2.6-1t-free` — 1T MoE

**Notes:** This is the default/built-in provider for opencode users. No separate account or API key needed — just use opencode. The provider ID in opencode is `opencode-zen`. Models with `-free` suffix are explicitly free tiers; others may have usage limits.