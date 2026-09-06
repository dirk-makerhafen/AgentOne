---
name: Mistral AI
url: "https://mistral.ai"
setup_instructions: |
  1. Create an account at https://console.mistral.ai (Free mode is the default state for new accounts; no credit card required).
  2. Open Studio > API keys at https://console.mistral.ai/api-keys.
  3. Click "Create new key", give it a name, and copy the key (it is shown only once).
  4. Export it as MISTRAL_API_KEY and call the API at https://api.mistral.ai/v1.
api_key_url: "https://console.mistral.ai/api-keys"
limits: {}
---

Mistral's La Plateforme (Studio) API defaults new organizations to Free mode with included monthly API usage for evaluation and prototyping.

**Free Tier:**

- Permanent free tier ("Free mode"), not expiring trial credits (verified 2026-09-05).
- Included monthly usage per plan, visible only behind login (Admin Panel > Subscriptions; per-model caps on Admin Panel > API > Limits). Previously reported "$10/mo Free" figures are **unverified on current official docs** and not recorded here.
- When included usage is exhausted without pay-as-you-go enabled, usage can stop until the next billing period.

**Free Models:**

- Labs (`labs-` prefix) models are the only officially-designated free-of-charge models: experimental, limited-time, not for production, subject to change, removable on short notice (current Labs page: 2 weeks' notice — verified 2026-09-05).
- `labs-devstral-small-2512` (previously listed here as the free model) is **retired as of 3/31/2026** per the official model-deprecation table — do not use. `labs-mistral-small-creative` retired 4/30/2026; `labs-leanstral-2603` retired 6/30/2026 (successor: Leanstral 1.5).
- No currently-active `labs-` model ID is published by name on the open Labs page (the page shows only the retired `labs-devstral-small-2512` as a naming example) — check the model cards / `GET /v1/models` for a live `labs-` ID before building.
- Any Studio API model is usable within the included monthly Free-mode usage and the per-model rate limits shown on the account Limits page.
- `mistral-large-latest` — used in the official Free-mode quickstart (example only, not a free-model designation).
- Discovery-listed IDs (`mistral-medium-3-5`, `mistral-small-2603`, `mistral-large-2512`, `ministral-8b-2512`, `codestral-2508`, `ministral-3b-2512`, `ministral-14b-2512`) and discovery figures ("~1 RPS, 500K TPM", "~1B tokens/month", "Experiment tier") are **secondary and unverified**.
- None of the catalogued model cards is served through this provider — no model-card links apply.

**Limits:**

- Exact public RPS/TPM/TPMo figures: **unknown** — official docs state limits are per organization, per model, and visible only on Admin Panel > API > Limits, so frontmatter `limits` is intentionally left empty.
- Enforcement model (documented, verified 2026-09-05): requests/second, tokens/minute, and tokens/month caps; `429` when exceeded; `402` when allowance/payment is exhausted; spending-limit breach can suspend API access until next month.

**Notes:**

- Account required; API key required; no credit card required for Free mode; phone verification: **unknown** (one secondary source reports SMS-only verification — unverified).
- OpenAI-compatible: point an OpenAI client at `base_url="https://api.mistral.ai/v1"`; native endpoint `POST https://api.mistral.ai/v1/chat/completions`.
- Data training: Free-mode prompts may be used to improve Mistral models unless the user opts out (Admin panel > Privacy > disable "Anonymous improvement data"); pay-as-you-go customers are opted out by default.
- Rate limits apply per organization across all workspaces, per model; retired-model migrations may change limits.

**Sources**

- https://docs.mistral.ai/inference/labs (Labs free-of-charge policy — verified 2026-09-05)
- https://docs.mistral.ai/models/labs (Labs policy, 2-weeks notice — verified 2026-09-05)
- https://docs.mistral.ai/admin/billing-usage/usage-limits (Free mode, Limits page, 429/402 semantics — verified 2026-09-05)
- https://docs.mistral.ai/inference/model-lifecycle
- https://docs.mistral.ai/models (deprecation table: labs-devstral-small-2512 retired 3/31/2026 — verified 2026-09-05)
- https://mistral.ai/pricing/
- https://help.mistral.ai/en/articles/698531-why-am-i-hitting-api-rate-limits-and-how-do-i-increase-them
- https://help.mistral.ai/en/articles/455207-can-i-opt-out-of-my-input-or-output-data-being-used-for-training
- Secondary (unverified figures only): docs/free-tier-research/raw/awesome-free-llm-apis/Mistral AI.json
