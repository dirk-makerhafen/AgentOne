---
name: Moark
url: "https://moark.ai"
api_base: "https://api.moark.ai/v1"
setup_instructions: |
  1. Go to https://moark.ai and click Login (redirects to Gitee — register a Gitee account first if needed). Each account gets up to 100 free model calls/day.
  2. A "Free Trial Access Token" is auto-created for your account (experience-only; cannot be edited or deleted). For a custom token, go to Dashboard -> Settings -> Access Token and create one.
  3. Call the OpenAI-compatible API at https://api.moark.ai/v1 with the token (e.g. POST https://api.moark.ai/v1/chat/completions).
  4. Stay within 100 free calls/day; buy a resource pack and use a paid token for more.
api_key_url: "https://moark.ai/dashboard/settings/tokens"
limits:
  requests:
    day: 100
---

Moark documents a "Free Trial Access Token" with 100 free calls/day on an ongoing daily cap; a paid resource pack applies beyond that (verified 2026-09-05).

**Free Tier:**

- 100 free calls/day per account via the auto-created Free Trial Access Token (daily cap; exceeding it returns "Today's free API access limit has been exceeded").
- The trial token is for experience/prototyping, not production; using it incurs no charges. For production, purchase a resource package and use a paid token.
- No concurrency limit is documented for the Serverless API (unified compute pool).

**Free Models:**

- All featured marketplace models are triable with the free token (resolve live at https://moark.ai/serverless-api); docs cite `Qwen3-8B` / `Qwen3-4B` as free models for rapid prototyping, and `Qwen2.5-72B-Instruct` in the API examples.
- Fixture rows `GLM-4.7` (`GLM-4.7`) and `MiniMax-M2.1` (`MiniMax-M2.1`) carry per-token costs in fixture data (paid resource packages), not the free set — do not treat them as free.

**Limits:**

- 100 requests/day (free token). Per-minute numerics: unknown.

**Notes:**

- Account required (Gitee-backed login); access token required; no payment for trial use.
- Correct endpoint is `https://api.moark.ai/v1` (official docs, verified 2026-09-05); the fixture-reported `https://moark.com/v1` is wrong.
- OpenCode integration docs recommend `MiniMax-M2.1` / `GLM-4.7` as configured models, but those are paid-listed — free-trial use should target marketplace featured/free models.
- Verification is thin (FAQ + getting-started + text-generation docs); treat as fragile and re-confirm before use.

**Sources**

- https://moark.ai/docs/appendix/qa (100 free calls/day, daily-limit error verified 2026-09-05)
- https://moark.ai/docs/getting-started (Gitee signup, 100 free calls/day, endpoint https://api.moark.ai/v1 verified 2026-09-05)
- https://moark.ai/docs/organization/access-token (auto-created trial token terms verified 2026-09-05)
- https://moark.ai/docs/products/apis/texts/text-generation (endpoint, Qwen3-8B/Qwen3-4B free prototyping models verified 2026-09-05)
