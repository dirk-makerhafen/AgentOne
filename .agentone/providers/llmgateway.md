---
name: LLM Gateway
url: "https://llmgateway.io"
api_base: "https://api.llmgateway.io/v1"
setup_instructions: |
  1. Sign up for a free account at https://llmgateway.io (email, GitHub, Google, or passkey — no credit card required to start).
  2. In the dashboard, create a new Project, go to API Keys, and create a key (LLM_GATEWAY_API_KEY, shown in full only once).
  3. Point an OpenAI-compatible client at https://api.llmgateway.io/v1 and call a free-tier model — no credit purchase needed.
api_key_url: "https://llmgateway.io/dashboard"
limits: {}
---

LLM Gateway (open source, AGPLv3) is an OpenAI-compatible gateway: "Free models are available on the free tier without buying credits." Paid use is prepaid credits ($10 minimum top-up) plus a flat 5% platform fee.

**Free Tier:**

- Free-tier (zero-price) models usable with $0 subscription and no credit purchase.
- Pricing page (verified 2026-09-05): Free plan is "$0 forever" with 3 rate-limited free models; no credit card required to start.
- BYOK (own provider keys) and self-hosting are free.

**Free Models:**

- No free chat-model ID is verifiable in the live catalog today (2026-09-05): the public `GET /v1/models` catalog lists 258 models with none flagged `free:true`, and the previously fixture-observed `claude-haiku-4-5-free` ($0 in/out) is absent — only paid `claude-haiku-4-5` variants remain.
- Resolve the current free set live via `GET https://api.llmgateway.io/v1/models` (public, no key; `free` flag per entry) or https://llmgateway.io/models — do not hardcode IDs from fixtures.

**Limits:**

- Documented free-model rate limits (verified 2026-09-05): organizations with zero credits get 5 requests per 10 minutes across all free-model requests (10-minute reset); organizations that have purchased credits get 20 requests per minute (credits are not deducted for free-model calls).
- Frontmatter limits omitted deliberately: the zero-credit figure (5 per 10 minutes) has no matching schema period and must not be re-derived, and the 20/minute figure only applies after a credit purchase, so neither is a provider-wide default.
- Paid-model endpoints are not rate-limited at the gateway beyond per-endpoint RPM caps and trust-tier spend caps (see rate-limits doc).

**Notes:**

- Account required; API key required (`llmgtwy_...`, per-project, bearer auth).
- Related paid products on the same platform: DevPass coding plans, Lounge chat memberships (not free API).
- Fixture lead (not authoritative, unverified live): `claude-haiku-4-5-free` at $0 in/out in `raw/opencode-models-api/llmgateway/` — re-check the live catalog before use, as it is gone as of 2026-09-05.

**Sources**

- https://llmgateway.io/pricing (free-tier sentence, $0-forever plan, 3 free models, verified 2026-09-05)
- https://docs.llmgateway.io/resources/rate-limits (free-model base/elevated limits, verified 2026-09-05)
- https://docs.llmgateway.io/quick-start (signup, project key, `https://api.llmgateway.io/v1` endpoint, verified 2026-09-05)
- https://docs.llmgateway.io/features/api-keys (dashboard key creation, verified 2026-09-05)
- https://api.llmgateway.io/v1/models (live catalog queried 2026-09-05: 258 models, none `free:true`)
