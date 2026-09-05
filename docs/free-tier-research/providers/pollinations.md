---
name: Pollinations.ai
url: "https://pollinations.ai/"
setup_instructions: |
  1. Sign in at https://enter.pollinations.ai/ (account dashboard; the OAuth consent screen offers GitHub sign-in).
  2. Earn free Pollen via Quests (see https://enter.pollinations.ai/news) and create a secret API key at https://enter.pollinations.ai/keys (`sk_` for backends; `pk_` App Keys are OAuth client IDs for apps where users spend their own Pollen).
  3. Call https://gen.pollinations.ai/v1/chat/completions with header `Authorization: Bearer YOUR_KEY` (OpenAI-compatible). The model catalog at GET https://gen.pollinations.ai/v1/models is public (no key needed).
api_key_url: "https://enter.pollinations.ai/keys"
limits: {}
---

Pollinations.ai is an open-source Berlin-based API for text, image, video, and audio generation with OpenAI-compatible endpoints, gated by Pollen credits with free Pollen earned via Quests.

**Free Tier:**

- Persistent but capped: free Pollen from Quests ("Free Pollen for prototypes & testing") — not unlimited, not a one-time trial.
- Keyless generation is gone: the official APIDOCS (verified 2026-09-05) requires a Bearer key for everything except public media reads and the model catalog; legacy keyless GET endpoints are deprecated/transitional.
- Paid top-ups exist alongside Quest Pollen; the "$1 = 1 Pollen" conversion is secondary-reported and unverified against official docs.

**Free Models:**

- No fixed free-model list: any model priced at zero Pollen is free ("a zero price makes the public model free") — resolve live at `GET https://gen.pollinations.ai/v1/models` or https://enter.pollinations.ai/models (representative, verify live).
- Text catalog snapshot from the official APIDOCS (verified 2026-09-05): `openai`, `openai-fast`, `gpt-oss`, `mercury`, `inception/mercury-2.5-preview`, `command-a-plus`, `qwen-coder`, `mistral-small-3.2`, `mistral`, `gemini-3-flash`, `gemini-flash-lite-3.5`, `deepseek`, `deepseek-pro`, `deepseek/deepseek-v4-flash-vision-exp`, `gemma`, `gemma-4-31b`, `laguna` (possibly a Poolside Laguna model — equivalence to [Laguna S 2.1](../models/laguna-s-2.1.md) / [Laguna XS 2.1](../models/laguna-xs-2.1.md) unverified, confirm live), `nemotron`, `minimax`, `minimax-m2.7`, `glm`, [`kimi-k3`](../models/kimi-k3.md), `grok`, `claude` variants, `llama` variants, `qwen3.7`/`qwen3.8` variants, `step-flash`.
- `kimi-k3` matches [kimi-k3](../models/kimi-k3.md) (confirm zero-Pollen price live); other IDs match no card exactly (cards use e.g. `google/gemma-4-31b-it`, `minimax-m3`, `deepseek-v4-flash`), so no other card links apply; do not assume equivalence from name similarity.

**Limits:**

- No published RPM/RPD/TPM figures. Binding constraints are Pollen balance, per-key model scoping/budgets, and `Retry-After` backoff on 429/503 (official APIDOCS, verified 2026-09-05). HTTP 402 means the key authenticated but the account or per-key budget is exhausted.
- Legacy raw `pk_` keys (no app/OAuth binding): rate-limited to 1 Pollen per IP per hour; do not mint new ones (official APIDOCS, verified 2026-09-05).
- Tier-grant figures are secondary/unverified (from 2025–2026 community sources; current site leads with Quests): Spore ~0.01 pollen/hr non-accumulating, Seed ~0.15/hr, Flower ~10/day, Nectar ~500/day.
- Check live balance/usage via the Account endpoints documented in APIDOCS.

**Notes:**

- Account required; API key required (`sk_` server-side, `pk_` App Keys as OAuth client IDs for user-wallet flows; never expose `sk_` publicly).
- Credit card: not documented for free use (unknown). Phone verification: unknown.
- App builders can use Connect-User-Wallets so end users spend their own Pollen (OAuth code flow + PKCE, or device flow for CLIs); developers can earn a revenue share via App Keys (25% markup opt-in per App Key).
- Community models in alpha (allowlist-only publishing).
- Data usage/training policy: unknown.

**Sources**

- https://github.com/pollinations/pollinations/blob/main/APIDOCS.md (authentication, key types, text model list, 402/429 semantics, raw-pk_ limit — verified 2026-09-05)
- https://github.com/pollinations/pollinations/blob/main/BRING_YOUR_OWN_POLLEN.md (GitHub sign-in, App Keys, OAuth/device flows, earnings — verified 2026-09-05)
- https://pollinations.ai/pricing (Pollen Quests, free Pollen for prototypes & testing — verified 2026-09-05)
- https://enter.pollinations.ai/ (dashboard, Quests, community-models alpha — verified 2026-09-05)
- https://pollinations.ai/docs (playground: API key required for generation — verified 2026-09-05)
- https://github.com/pollinations/pollinations/issues/8925 (secondary, tier mechanics)
