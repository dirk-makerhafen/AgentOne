---
name: Fireworks AI
url: "https://fireworks.ai"
api_base: "https://api.fireworks.ai/inference/v1/"
setup_instructions: |
  1. Sign up at https://fireworks.ai (free credits for new users).
  2. Create an API key at https://fireworks.ai/account/api-keys.
  3. Call the OpenAI-compatible endpoint at https://api.fireworks.ai/inference/v1/ with the key as Bearer token.
api_key_url: "https://fireworks.ai/account/api-keys"
limits:
  requests:
    minute: 60
    day: 1000
---

Fireworks AI is an inference platform with 28 models in opencode fixtures. Only 1 model is free; most are pay-as-you-go at competitive rates. Free credits for new signups.

**Free Tier:**

- New user credits (amount varies, typically $1-5 equivalent).
- 1 free model available: `accounts/fireworks/routers/kimi-k2p5-turbo` (Kimi K2.5 Turbo router).
- 60 RPM, 1,000 RPD estimated for free tier.

**Free Model (verified 2026-10-27 from opencode fixtures):**

- `accounts/fireworks/routers/kimi-k2p5-turbo` — 256K context, reasoning, tool calls (Kimi K2.5 Turbo router)

**Paid Models (representative, verified 2026-10-27):**

- `accounts/fireworks/models/deepseek-v4-flash` — 1M context, $0.14/$0.28 per 1M
- `accounts/fireworks/models/deepseek-v4-pro` — 1M context, $1.74/$3.48 per 1M
- `accounts/fireworks/models/gpt-oss-120b` — 131K context, $0.15/$0.60 per 1M
- `accounts/fireworks/models/gpt-oss-20b` — 131K context, $0.05/$0.20 per 1M
- `accounts/fireworks/models/minimax-m3` — 512K context, $0.30/$1.20 per 1M
- `accounts/fireworks/models/glm-5` — 203K context, $1.00/$3.20 per 1M
- `accounts/fireworks/models/kimi-k2-thinking` — 256K context, $0.60/$2.50 per 1M
- `accounts/fireworks/routers/glm-5p2-fast` — 1M context, $2.10/$6.60 per 1M
- +18 more models (DeepSeek, GLM, Kimi, MiniMax, Qwen, GPT-OSS)

**Limits:**

- Free tier: limited credits, 1 free model only.
- Paid tier: pay-as-you-go per 1M tokens; rates vary by model.
- Rate limits: ~60 RPM, 1,000 RPD (estimated, not officially documented for free tier).
- Router models (e.g., `kimi-k2p5-turbo`) route to optimized backends.

**Notes:**

- Account and API key required; free credits on signup (no credit card initially).
- OpenAI-compatible: `https://api.fireworks.ai/inference/v1/`.
- Model IDs use Fireworks account format: `accounts/fireworks/models/{model}` or `accounts/fireworks/routers/{router}`.
- Competitive pricing for open-weight models; often cheaper than direct providers.
- Also accessible via Hugging Face Inference Providers (free credits route there).

**Sources**

- https://fireworks.ai (official site)
- https://fireworks.ai/docs/ (documentation)
- https://api.fireworks.ai/inference/v1/models (live model list, auth required)
- docs/free-tier-research/raw/opencode-models-api/fireworks-ai/ (28 model fixtures, 1 free, verified 2026-10-27)
- docs/free-tier-research/raw/awesome-free-llm-apis/Hugging Face.json (mentioned as inference provider)