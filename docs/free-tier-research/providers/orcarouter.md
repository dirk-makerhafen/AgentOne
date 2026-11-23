---
name: OrcaRouter
url: https://www.orcarouter.ai
api_base: https://api.orcarouter.ai/v1
setup_instructions: '1. Sign up at https://www.orcarouter.ai with GitHub (Hacker tier
  is free forever, no credit card).

  2. Create an API key (Hacker tier includes 3 keys).

  3. Point an OpenAI-compatible client at https://api.orcarouter.ai/v1 and call a
  `-free` model ID (e.g. `deepseek/deepseek-v4-flash-free`) or the `orcarouter/free`
  named router. If the key has an allowed-model list, add `orcarouter/free` itself
  — whitelisting pool members does not unlock the router.

  '
api_key_url: https://www.orcarouter.ai
---

OrcaRouter is an AI gateway (200+ models, one OpenAI-compatible API) whose Hacker tier is free forever with no credit card. Models with IDs ending in `-free` are ordinary catalog models priced at $0 — same weights and capabilities as the paid model they shadow — plus a built-in `orcarouter/free` named router over the free tier.

**Sources**

- https://docs.orcarouter.ai/routing/free-models (free IDs, unpublished limits, 429 handling verified 2026-09-05)
- https://www.orcarouter.ai/models/orcarouter/free (router behavior, per-account/per-model rates verified 2026-09-05)
- https://www.orcarouter.ai/pricing (Hacker free-forever, $0 markup, no card verified 2026-09-05)
- https://docs.orcarouter.ai/routing/auto-router (seeded `orcarouter/auto` is not a free model)
- https://docs.orcarouter.ai/routing/named-routers (`prefer_free` package vs `-free` catalog distinction)
