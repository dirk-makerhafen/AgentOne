---
name: Gonka Broker
url: "https://gonkabroker.com"
api_base: "https://proxy.gonkabroker.com/v1"
setup_instructions: |
  1. Sign up at https://app.gonkabroker.com/signup (phone verification required; free tier is $0, no credit card).
  2. Create an API key in the dashboard.
  3. Call the OpenAI-compatible endpoint at https://proxy.gonkabroker.com/v1 with the key as Bearer token.
  4. Live model list available at GET /v1/models (rotates with network governance).
api_key_url: "https://app.gonkabroker.com/signup"
limits:
  tokens:
    month: 1000000
---

Gonka Broker is a decentralized inference broker with a permanent free tier (~1M tokens/month shared across models, resets monthly). Model lineup rotates with network governance; check `/v1/models` for current availability.

**Free Tier:**

- Permanent free tier, no credit card required; phone verification required.
- ~1M tokens/month shared quota (varies by model), resets monthly.
- Live model list at `/v1/models` (rotates with network governance).

**Free Models (verified 2026-09-05):**

- `MiniMaxAI/MiniMax-M2.7` — 200K context, 16K max output, reasoning.
- `deepseek-ai/DeepSeek-V4-Flash-0731` — 400K context, 16K max output, reasoning.
- `zai-org/GLM-5.3-Flash` — 400K context, 16K max output, reasoning.
- `BAAI/bge-m3` — 8K context, embeddings.

**Limits:**

- Shared token quota: ~1M tokens/month (varies by model).
- 429 when quota exhausted; resets monthly.
- Model availability changes with network governance.

**Notes:**

- Account required; API key required; phone verification required; no credit card.
- OpenAI-compatible: `https://proxy.gonkabroker.com/v1`.
- Model IDs use provider/name format (e.g., `MiniMaxAI/MiniMax-M2.7`).
- No model-card links currently catalogued for these specific variants.

**Sources**

- https://gonkabroker.com (official site)
- https://app.gonkabroker.com/signup (signup)
- https://proxy.gonkabroker.com/v1/models (live model list)
- docs/free-tier-research/raw/awesome-free-llm-apis/Gonka Broker.json (discovery snapshot, verified 2026-09-05)