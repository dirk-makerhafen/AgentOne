---
name: Logfare
url: "https://logfare.ai"
api_base: "https://logfare.ai/v1"
setup_instructions: |
  1. Register at https://logfare.ai/register (no card) and keep your account in the Logfare Discord server; leaving suspends access.
  2. Save the API key shown once at signup.
  3. Point an OpenAI-compatible client at https://logfare.ai/v1 and call `logfare/auto` or another available model.
  4. Check GET /v1/models for the current model list; ids change often.
api_key_url: "https://logfare.ai/register"
limits:
  requests:
    minute: 40
    hour: 1000
    day: 5000
---

Logfare is a free research-oriented LLM gateway with unusually thorough official docs. Account + key required, no payment. **All API traffic is logged for research; the site explicitly says not to send private data.** Verified 2026-11-20.

**Free Tier:**

- Standard (free, account only): 40 RPM / 1,000 per hour / 5,000 per day / 6 concurrent (official auto-updating table).
- New accounts (first 24h): 10 RPM / 200 per hour / 500 per day / 2 concurrent.
- Shared IP/network ceiling: 320 RPM / 8,000 per hour / 40,000 per day; the lower of account and network wins.
- Discord server membership is required to retain access. Discord boosts add +50% request allowance each (max 4 counted) and +12 concurrency each.
- Premium/Pro tiers remain monetary-free but require opting into model training or data sale; they are not required for the Standard lane.

**Free Models:**

- `logfare/auto` — documented alias router; picks the best available model and fails over. Context is served per-model (catalog reports 131,072, not officially fixed).
- `gemma-4-26b` — listed on the Standard (Free) tier.
- Catalog-only rows `glm-5.3`, `glm-5.3-flash`, `kimi-k3`, `kimi-k2.6`, `qwen-3.8-27b`, `moondream3.1` currently return `403` premium; `mimo-v2.5` hit an account rate limit. Treat `GET /v1/models` as authoritative.

**Limits:**

- Frontmatter uses the Standard-tier documented limits. No token quota is published.

**Notes:**

- Privacy is the defining caveat: routine request/response logging continues even after opting out of training/eval at `/consent`. Do not send sensitive content.
- Multiple transports are documented: `/v1/chat/completions`, `/v1/responses`, `/v1/messages`.
- Usage reports a `neurons` field; responses may include reasoning content.
- One account per person (fair use). Keys are shown only once.

**Sources**

- https://logfare.ai
- https://logfare.ai/docs
- https://logfare.ai/models
- https://logfare.ai/tos
- https://logfare.ai/privacy
- https://logfare.ai/consent
- docs/free-tier-research/raw/freellmapi-catalog/platforms/logfare.json (discovery lead, verified 2026-11-20)
