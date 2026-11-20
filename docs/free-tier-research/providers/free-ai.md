---
name: Free.ai
url: "https://free.ai"
api_base: "https://api.free.ai"
setup_instructions: |
  1. Enter your email at https://free.ai/api and confirm the sign-in link (no card, no password).
  2. Generate an `sk-free-...` key.
  3. POST to https://api.free.ai/v1/chat/ with `Authorization: Bearer sk-free-...` and `model: "qwen7b"`.
  4. Only self-hosted models are free; `premium/...` and external models consume purchased tokens.
api_key_url: "https://free.ai/api"
limits:
  requests:
    minute: 60
    month: 1000
  tokens:
    day: 30000
---

Free.ai (Muddy Holdings LLC) is an aggregator with a genuine free allowance on its self-hosted models. Account + key required for the 30K/day allowance; no card. Verified 2026-11-20.

**Free Tier:**

- Free plan: 30,000 tokens/day shared pool, 1,000 API requests/month, 60 API requests/minute, $0. Exhaustion returns `402`; wait for the daily reset.
- The models page also advertises 6,000 tokens/day without an account (web use).
- Only self-hosted models are free; external models use a 1.5× token-unit markup and consume purchased tokens.
- Docs conflict on key issuance ("purchase tokens, then generate your key" in How It Works vs. Free $0 in FAQ/pricing). Key generation details are **partially verified**.

**Free Models:**

- `qwen7b` — Qwen 3.6 35B, type chat, self-hosted, zero input/output price, 16K context. Primary verified free chat model.
- Other zero-priced self-hosted aliases (mostly Qwen 3.6 35B variants): `qwen-coder`, `qwen3-coder`, `mistral`, `qwen3-8b`, `deepseek-r1`, `deepseek-r1-7b`.
- `kokoro` — self-hosted TTS, free within the daily pool.
- `qwen-vl`, `qwen25-vl`, `moondream2` are vision-type entries but have no pricing block in the models response; **do not claim free**.

**Limits:**

- Frontmatter uses the official pricing-table figures. No RPM beyond 60/min is published.

**Notes:**

- Endpoints use trailing slashes (`/v1/chat/`, `/v1/tts/`); the chat body is OpenAI-shaped but the path is **not** `/v1/chat/completions`. AgentOne's standard `openai/` + `api_base` path will not call this correctly without an adapter.
- Many aliases misleadingly report the same display name "Qwen 3.6 35B".
- Tool/vision support for the free chat aliases is unverified.

**Sources**

- https://free.ai/api
- https://api.free.ai/v1/models
- https://free.ai/models
- https://free.ai/docs
- docs/free-tier-research/raw/freellmapi-catalog/platforms/freeai.json (discovery lead, verified 2026-11-20)
