---
name: Pollinations.ai
url: https://pollinations.ai/
api_base: https://gen.pollinations.ai/v1
setup_instructions: '1. Sign in at https://enter.pollinations.ai/ (account dashboard;
  the OAuth consent screen offers GitHub sign-in).

  2. Earn free Pollen via Quests (see https://enter.pollinations.ai/news) and create
  a secret API key at https://enter.pollinations.ai/keys (`sk_` for backends; `pk_`
  App Keys are OAuth client IDs for apps where users spend their own Pollen).

  3. Call https://gen.pollinations.ai/v1/chat/completions with header `Authorization:
  Bearer YOUR_KEY` (OpenAI-compatible). The model catalog at GET https://gen.pollinations.ai/v1/models
  is public (no key needed).

  '
api_key_url: https://enter.pollinations.ai/keys
---

Pollinations.ai is an open-source Berlin-based API for text, image, video, and audio generation with OpenAI-compatible endpoints, gated by Pollen credits with free Pollen earned via Quests.

**Sources**

- https://github.com/pollinations/pollinations/blob/main/APIDOCS.md (authentication, key types, text model list, 402/429 semantics, raw-pk_ limit — verified 2026-09-05)
- https://github.com/pollinations/pollinations/blob/main/BRING_YOUR_OWN_POLLEN.md (GitHub sign-in, App Keys, OAuth/device flows, earnings — verified 2026-09-05)
- https://pollinations.ai/pricing (Pollen Quests, free Pollen for prototypes & testing — verified 2026-09-05)
- https://enter.pollinations.ai/ (dashboard, Quests, community-models alpha — verified 2026-09-05)
- https://pollinations.ai/docs (playground: API key required for generation — verified 2026-09-05)
- https://github.com/pollinations/pollinations/issues/8925 (secondary, tier mechanics)
