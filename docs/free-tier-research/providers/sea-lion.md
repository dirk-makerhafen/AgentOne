---
name: SEA-LION
url: "https://sea-lion.ai"
api_base: "https://api.sea-lion.ai/v1"
setup_instructions: |
  1. Sign in to the SEA-LION Playground with a Google account at https://playground.sea-lion.ai.
  2. Open Key Manager and create a New Trial API Key (only one key per user).
  3. Point an OpenAI-compatible client at https://api.sea-lion.ai/v1 with that key.
  4. Use GET /v1/models with the key to discover the currently callable model ids.
api_key_url: "https://playground.sea-lion.ai/key-manager"
limits:
  requests:
    minute: 10
---

SEA-LION is AI Singapore's first-party API for its Southeast-Asian language models. The official FAQ documents a free POC/prototyping API at 10 requests/minute per account, with no card requirement and no published expiry or token budget. Limits cannot be raised.

**Free Tier:**

- 10 requests/minute per account (official FAQ, verified 2026-11-20).
- Google sign-in + one trial API key required; no card, no region wall.
- Intended for POC/prototyping, not production.

**Free Models:**

- `aisingapore/Qwen-SEA-LION-v4.5-27B-IT` — official API example and v4.5 docs; 262K context, reasoning/agentic tool use. This is the only id confirmed from official docs (catalog's 32K context and `supportsTools=false` are stale and overridden).
- Catalog-reported ids to confirm via authenticated `GET /v1/models`: `aisingapore/Qwen-SEA-LION-v4-32B-IT`, `aisingapore/Gemma-SEA-LION-v4-27B-IT`, `aisingapore/Llama-SEA-LION-v3-70B-IT`, `aisingapore/Nemotron-SEA-LION-v4.8-120B-A12B`.
- `aisingapore/SEA-Guard` is a moderation/safety-label model, not a chat-completion assistant; catalog flags it as a chat row, but official docs describe it differently.

**Limits:**

- 10 RPM provider-wide; no RPD, TPM, or TPD published. Do not infer them.

**Notes:**

- An embedding model, `aisingapore/SEA-LION-ModernBERT-Embedding-600M`, is documented for the same key (8K context, 1024 dimensions, 11 SEA languages); it is not a chat model.
- v3.5 reasoning models use a `thinking_mode` chat-template flag ("on"/"off"); v4.5 adds agentic tool use.
- Free model roster is key-gated; do not assume every catalog row is currently callable.

**Sources**

- https://docs.sea-lion.ai/guides/inferencing/api
- https://docs.sea-lion.ai/overview/readme/faq.md
- https://sea-lion.ai/try-sea-lion
- https://docs.sea-lion.ai/models/sea-lion-v4.5
- docs/free-tier-research/raw/freellmapi-catalog/platforms/sealion.json (discovery lead, verified 2026-11-20)
