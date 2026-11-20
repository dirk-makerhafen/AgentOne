---
name: Septor Labs
url: "https://septorlabs.com"
api_base: "https://api.septorlabs.com/v1"
setup_instructions: |
  1. Register at https://septorlabs.com/register (no card required).
  2. In the dashboard, create an API key (`sk-...`).
  3. Point an OpenAI-compatible client at https://api.septorlabs.com/v1 and call a `-free` model id.
api_key_url: "https://septorlabs.com/register"
limits:
  requests:
    minute: 20
    day: 50
  tokens:
    minute: 100000
    day: 250000
---

Septor Labs is an OpenAI-compatible router with a recurring free lane for selected `-free` models. The recurring allowance is independent of a one-time $1 signup credit and does not require a card. Verified 2026-11-20.

**Free Tier:**

- Free models: **50 requests/day + 250,000 tokens/day** (pricing.md and homepage). The HTML pricing page says 500K tokens/day; the 250K figure is used here because it is repeated in the machine-readable pricing file and current catalog. Treat 500K as an unresolved official-source conflict.
- Free plan rate limit: 20 requests/minute and 100,000 tokens/minute (rate-limits page).
- Account + API key required; no card. The $1 signup credit (90-day TTL) is one-time and explicitly **excluded** from this free assessment.
- A first $10 PAYG purchase raises free-model requests to 200/day even at $0 balance; that is a paid-gated enhancement, not the standing free tier.

**Free Models:**

- `hermes-3-llama-3.1-405b-free` — 128K context, tools/JSON supported, text only.
- `minimax-m2.5-free` — 128K context, tools/JSON supported, text only.
- `qwen3-coder-free` — 128K context, tools/JSON supported, text only.
- `qwen3-next-80b-a3b-instruct-free` — 128K context, tools/JSON supported, text only.
- `gemma-4-31b-it-free` — 128K context, no tool/JSON tag, text only.
- The official model catalog also lists other "(Free)" display names (e.g. GLM 5.3 Flash, Qwen3.8 27B, Mistral Small 4, Command family); those are expansion leads, not verified here.

**Limits:**

- Provider-wide frontmatter values are the recurring free-model allowance plus the free-plan rate limit.
- Semantically cached calls are opt-in (`cache: true`), PII-redacted, and billed at a 30% discount; they are not free.

**Notes:**

- Critical quirk: on 2026-09-18 most ad-hoc `-free` aliases silently answered as `minimax-m2.5-free`. Only the five ids above were re-verified as returning matching ids with `usage.cost=0`. Always compare the responding model id before trusting a Septor alias.
- Tool flags are provider-advertised and were not live-tested.
- The docs' SDK snippets omit `https://` and `/v1`; curl examples use `/v1/...` and are authoritative for the base URL.

**Sources**

- https://septorlabs.com/pricing.md
- https://septorlabs.com/models
- https://septorlabs.com/docs/rate-limits
- https://septorlabs.com/docs/pricing
- https://septorlabs.com/api/openapi.json
- docs/free-tier-research/raw/freellmapi-catalog/platforms/septor.json (discovery lead, verified 2026-11-20)
