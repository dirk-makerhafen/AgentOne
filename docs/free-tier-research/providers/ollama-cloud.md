---
name: Ollama Cloud
url: "https://ollama.com/cloud"
api_base: "https://ollama.com/api"
setup_instructions: |
  1. Sign up at https://ollama.com/cloud (GitHub/Google/email; free tier included).
  2. Create an API key in the Ollama Cloud dashboard.
  3. Call the OpenAI-compatible endpoint at https://ollama.com/api with the key as Bearer token.
api_key_url: "https://ollama.com/cloud"
limits:
  requests:
    minute: 20
    day: 10000
---

Ollama Cloud provides a free hosted inference tier (20 RPM, 10K RPD) with 100+ open-weight models. OpenAI-compatible API.

**Free Tier:**

- Free hosted inference tier (signup required, no credit card).
- 20 RPM, 10,000 RPD.
- 100+ open-weight models.

**Free Models (verified 2026-10-27 from opencode fixtures):**

### DeepSeek Family
- `deepseek-v4-flash` — 1M context, 1M max output, reasoning, tool calls, open weights (2026-04-24)
- `deepseek-v4-pro` — 1M context, 1M max output, reasoning, tool calls, open weights (2026-04-24)
- `deepseek-v3.1:671b` — 164K context, 164K max output, reasoning, tool calls, open weights (2025-08-21)
- `deepseek-v3.2` — 164K context, 66K max output, reasoning, tool calls, open weights (2025-06-15)

### GLM (Z.ai) Family
- `glm-5.2` — 976K context, 131K max output, reasoning, tool calls, open weights (2026-06-13)
- `glm-5.1` — 203K context, 131K max output, reasoning, tool calls, open weights (2026-03-27)
- `glm-5` — 203K context, 131K max output, reasoning, tool calls, open weights (2026-02-11)
- `glm-4.7` — 203K context, 131K max output, reasoning, tool calls, open weights (2025-12-22)
- `glm-4.6` — 203K context, 131K max output, reasoning, tool calls, open weights (2025-09-29)

### MiniMax Family
- `minimax-m3` — 512K context, 131K max output, reasoning, tool calls, vision+video, open weights (2026-05-31)
- `minimax-m2.7` — 205K context, 131K max output, reasoning, tool calls, open weights (2026-03-18)
- `minimax-m2.5` — 205K context, 131K max output, reasoning, tool calls, open weights (2026-02-12)
- `minimax-m2.1` — 205K context, 131K max output, reasoning, tool calls, open weights (2025-12-23)
- `minimax-m2` — 205K context, 128K max output, tool calls, open weights (2025-10-23)

### Nemotron (NVIDIA) Family
- `nemotron-3-nano:30b` — 1M context, 131K max output, reasoning, tool calls, open weights (2025-12-15)
- `nemotron-3-super` — 262K context, 66K max output, reasoning, tool calls, open weights (2026-03-11)
- `nemotron-3-ultra` — 262K context, 128K max output, reasoning, tool calls, open weights (2026-06-04)

### Qwen Family
- `qwen3.5:397b` — 262K context, 82K max output, reasoning, tool calls, vision, open weights (2026-02-15)
- `qwen3-next:80b` — 262K context, 33K max output, reasoning, tool calls, open weights (2025-09-15)
- `qwen3-coder:480b` — 262K context, 66K max output, tool calls, open weights (2025-07-22)
- `qwen3-coder-next` — 262K context, 66K max output, tool calls, open weights (2026-02-02)
- `qwen3-vl:235b-instruct` — 262K context, 131K max output, tool calls, vision, open weights (2025-09-22)
- `qwen3-vl:235b` — 262K context, 33K max output, reasoning, tool calls, vision, open weights (2025-09-22)

### Gemma (Google) Family
- `gemma4:31b` — 262K context, 262K max output, reasoning, tool calls, vision, open weights (2026-04-02)
- `gemma3:27b` — 131K context, 131K max output, vision, open weights (2025-07-27)
- `gemma3:12b` — 131K context, 131K max output, vision, open weights (2024-12-01)
- `gemma3:4b` — 131K context, 131K max output, vision, open weights (2024-12-01)

### Kimi (Moonshot) Family
- `kimi-k2.7-code` — 262K context, 262K max output, reasoning, tool calls, vision, open weights (2026-06-12)
- `kimi-k2.6` — 262K context, 262K max output, reasoning, tool calls, vision, open weights (2026-04-20)
- `kimi-k2.5` — 262K context, 262K max output, reasoning, tool calls, vision, open weights (2026-01-27)
- `kimi-k2-thinking` — 262K context, 262K max output, reasoning, tool calls, open weights (2025-11-06)
- `kimi-k2:1t` — 262K context, 262K max output, tool calls, open weights (2025-07-11)

### GPT-OSS (OpenAI) Family
- `gpt-oss:120b` — 131K context, 33K max output, reasoning, tool calls, open weights (2025-08-05)
- `gpt-oss:20b` — 131K context, 33K max output, reasoning, tool calls, open weights (2025-08-05)

### Mistral Family
- `mistral-large-3:675b` — 262K context, 262K max output, tool calls, vision, open weights (2025-12-02)
- `ministral-3:14b` — 262K context, 128K max output, tool calls, vision, open weights (2024-12-01)
- `ministral-3:8b` — 262K context, 128K max output, tool calls, vision, open weights (2024-12-01)
- `ministral-3:3b` — 262K context, 128K max output, tool calls, vision, open weights (2024-10-22)

### Devstral (Mistral) Family
- `devstral-2:123b` — 262K context, 262K max output, tool calls, open weights (2025-12-09)
- `devstral-small-2:24b` — 262K context, 262K max output, tool calls, vision, open weights (2025-12-09)

### Other Models
- `cogito-2.1:671b` — 164K context, 32K max output, reasoning, tool calls, open weights (2025-11-19)
- `gemini-3-flash-preview` — 1M context, 66K max output, reasoning, tool calls, open weights (2025-12-17)
- `rnj-1:8b` — 33K context, 4K max output, tool calls, open weights (2025-12-06)

**Limits:**

- 20 RPM, 10,000 RPD.
- 429 when quota exceeded.
- Models hosted on Ollama infrastructure.

**Notes:**

- Account required; API key required; no credit card.
- OpenAI-compatible: `https://ollama.com/api` (also `https://ollama.com/v1`).
- Live model catalog at https://ollama.com/library.
- Model IDs use Ollama's format with tags (e.g., `gemma3:27b`, `qwen3-coder:480b`).
- All models are open weights; many support reasoning and tool calling.

**Sources**

- https://ollama.com/cloud (official site)
- https://ollama.com/library (model library)
- https://ollama.com/api/models (live model list)
- docs/free-tier-research/raw/awesome-free-llm-apis/Ollama Cloud.json (discovery snapshot, verified 2026-09-05)
- docs/free-tier-research/raw/opencode-models-api/ollama-cloud/ (38 model fixtures, verified 2026-10-27)