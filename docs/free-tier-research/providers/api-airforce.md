---
name: Api.Airforce
url: "https://api.airforce"
api_base: "https://api.airforce/v1"
setup_instructions: |
  1. Create a free account at https://api.airforce/signup/ (no card).
  2. Create an `sk-air-...` API key under Dashboard -> API Keys (https://api.airforce/dashboard/#api-keys).
  3. Point an OpenAI-compatible client at https://api.airforce/v1 and call a free-tier model id.
api_key_url: "https://api.airforce/signup/"
limits:
  requests:
    minute: 1
    day: 1000
---

Api.Airforce is an OpenAI-compatible gateway with a standing $0 Free plan limited to free-tier models. Account + key required, no card. Verified 2026-11-20.

**Free Tier:**

- $0.00/month, free model access only, no credit pool on Free.
- 1 request/minute and 1,000 requests/day (official pricing and quickstart agree).
- Paid plan rate limits conflict between the quickstart (5 RPM Premium / 10 RPM Master) and the pricing page (20–120 RPM across tiers); the Free figures are consistent.

**Free Models:**

Only three official free models are currently operational:

- `kimi-k2.7-code` — official model page says Free with no per-token cost; live API `tier=free`, `status=operational`. No tools, no vision, no reasoning. API `max_tokens=4096`; context not exposed. An older catalog quirk claiming a paid-plan requirement is stale.
- `llama-instant` — official model page explicitly free/no token cost; live API operational. No tools, no vision, no reasoning. `max_tokens=4096`; context not exposed.
- `gpt-oss-20b` — official model page says Free/no token cost, 131K context, 33K max output, tools + reasoning, no vision. Live API operational, though the models page reports a major outage — status conflict. API `max_tokens=4096`.

Official free-tier ids currently marked `major_outage` in the live API (do not treat as usable): `codestral-2508`, `codestral-latest`, `gemma3-270m:free`, `ministral-14b-2512`, `ministral-14b-latest`, `ministral-3b-2512`, `ministral-3b-latest`, `ministral-8b-2512`, `ministral-8b-latest`, `mistral-code-fim-latest`, `mistral-code-latest`, `mistral-large-2512`, `mistral-large-latest`, `mistral-tiny-2407`, `mistral-tiny-latest`, `open-mistral-nemo`, `open-mistral-nemo-2407`, `voxtral-small-2507`, `voxtral-small-latest`.

Catalog-only ids `rnj-1` and `unmoderated-gpt` no longer appear in the live API. `mistral-large-4` is contradictory (model page says Free, live API says `paid_only`) and is excluded.

**Limits:**

- Frontmatter uses the Free plan's 1 RPM / 1,000 RPD. 1 RPM is very low — integrations need retry/backoff.
- `access_tiers: ["free"]` alone does not mean zero-cost; many paid-tier ids carry it with priced token tables.

**Notes:**

- Most free routes are reported to proxy Mistral free-plan capacity; many are currently in `major_outage`.
- Authenticated inference and zero-billing behavior were not live-tested.

**Sources**

- https://api.airforce/docs/quickstart
- https://api.airforce/docs
- https://api.airforce/pricing/
- https://api.airforce/signup/
- https://api.airforce/models/
- https://api.airforce/models/kimi-k2.7-code
- https://api.airforce/models/llama-instant
- https://api.airforce/models/gpt-oss-20b
- https://api.airforce/v1/models
- docs/free-tier-research/raw/freellmapi-catalog/platforms/airforce.json (discovery lead, verified 2026-11-20)
