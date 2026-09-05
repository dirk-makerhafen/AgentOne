---
name: Pollinations.ai
url: "https://pollinations.ai/"
setup_instructions: |
  1. Sign in at https://enter.pollinations.ai/.
  2. Earn starter Pollen via Quests (see https://enter.pollinations.ai/news) and create an API key at https://enter.pollinations.ai/keys (`sk_` for backends, `pk_` for frontends).
  3. Call https://gen.pollinations.ai/v1/chat/completions with header `Authorization: Bearer YOUR_KEY` (OpenAI-compatible).
api_key_url: "https://enter.pollinations.ai/keys"
limits: {}
---

Pollinations.ai is an open-source Berlin-based API for text, image, video, and audio generation with OpenAI-compatible endpoints, gated by Pollen credits ($1 = 1 Pollen) with free Pollen earned via Quests.

**Free Tier:**

- Persistent but capped: free Pollen from Quests ("Free Pollen for prototypes & testing") plus account tier grants — not unlimited, not a one-time trial.
- Legacy keyless GET endpoints are deprecated/transitional; current docs require an API key for generation.

**Free Models:**

- No fixed free-model list: any model priced at zero Pollen is free ("a zero price makes the public model free") — resolve live at `GET https://gen.pollinations.ai/v1/models` or https://enter.pollinations.ai/models (representative, verify live).
- Text catalog snapshot (representative, verify live): `openai`, `openai-fast`, `gpt-oss`, `gpt-5.4`, `gpt-5.4-mini`, `gemini-3-flash`, `gemini-flash-lite-3`, `mistral-small-3.2`, `mistral`, `qwen-coder`, `mercury`, `inception/mercury-2.5-preview`, `command-a-plus`.

**Limits:**

- No published RPM/RPD/TPM figures. Binding constraints are Pollen balance, per-key model scoping/budgets, and `Retry-After` backoff on 429/503.
- Tier-grant figures are secondary/unverified (from 2025–2026 community sources; current site leads with Quests): Spore ~0.01 pollen/hr non-accumulating, Seed ~0.15/hr, Flower ~10/day, Nectar ~500/day; publishable `pk_` keys ~1 pollen/IP/hour (third-party SDK docs).
- Check live balance/usage at `GET /account/balance` and `GET /account/usage`.

**Notes:**

- Account required; API key required (`sk_` server-side, `pk_` client-side; never expose `sk_` publicly).
- Credit card: not documented for free use (unknown). Phone verification: unknown.
- App builders can use Connect-User-Wallets so end users spend their own Pollen; developers can earn a revenue share via App Keys.
- Community models in alpha (allowlist-only publishing).
- Data usage/training policy: unknown.

**Sources**

- https://gen.pollinations.ai/docs (API reference)
- https://github.com/pollinations/pollinations/blob/main/APIDOCS.md
- https://pollinations.ai/pricing
- https://enter.pollinations.ai/
- https://github.com/pollinations/pollinations (repo)
- https://github.com/pollinations/pollinations/issues/8925 (secondary, tier mechanics)
