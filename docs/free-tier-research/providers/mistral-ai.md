---
name: Mistral AI
url: "https://mistral.ai"
setup_instructions: |
  1. Create an account at https://console.mistral.ai (Free mode is the default state for new accounts; no credit card required).
  2. Open Studio > API keys at https://console.mistral.ai/api-keys.
  3. Click "Create new key", give it a name, and copy the key (it is shown only once).
  4. Export it as MISTRAL_API_KEY and call the API at https://api.mistral.ai/v1.
api_key_url: "https://console.mistral.ai/api-keys"
limits:
---

Mistral's La Plateforme (Studio) API defaults new organizations to Free mode with included monthly API usage for evaluation and prototyping.

**Free Tier:**

- Permanent free tier ("Free mode"), not expiring trial credits.
- Included monthly usage per plan, visible only behind login (Admin Panel > Subscription, or API > Limits); previously reported "$10/mo Free / $30/mo Pro" figures are **unverified on current official docs** and removed here.
- When included usage is exhausted without pay-as-you-go enabled, usage can stop until the next billing period.

**Free Models:**

- No fixed free-model list is published; any Studio API model is usable within the included monthly usage and the per-model rate limits shown on the account Limits page.
- `mistral-large-latest` — used in the official Free-mode quickstart (example only, not a free-model designation).
- Discovery-listed IDs (`mistral-medium-3-5`, `mistral-small-2603`, `mistral-large-2512`, `ministral-8b-2512`, `codestral-2508`, `ministral-3b-2512`, `ministral-14b-2512`) are **unverified in official docs**.

**Limits:**

- Exact public RPS/TPM/TPMo figures: **unknown** — official docs state limits are per organization, per model, and visible only on Admin Panel > API > Limits.
- Enforcement model (documented): requests/second, tokens/minute, and tokens/month caps; `429` when exceeded; `402` when allowance/payment is exhausted.
- Discovery claim of "~1 RPS, 500K TPM" is **secondary and unverified**.

**Notes:**

- Account required; API key required; no credit card required for Free mode; phone verification: **unknown**.
- OpenAI-compatible: point an OpenAI client at `base_url="https://api.mistral.ai/v1"`; native endpoint `POST https://api.mistral.ai/v1/chat/completions`.
- Data training: Free-mode prompts may be used to improve Mistral models unless the user opts out (Admin panel > Privacy > disable "Anonymous improvement data"); pay-as-you-go customers are opted out by default.
- Rate limits apply per organization across all workspaces, per model; retired-model migrations may change limits.

**Sources**

- https://docs.mistral.ai/ (getting-started quickstart: first-api-request; admin/billing-usage/subscriptions; admin/billing-usage/usage-limits; resources/migration-guides; /api chat endpoints)
- https://mistral.ai/pricing/
- https://help.mistral.ai/en/articles/698531-why-am-i-hitting-api-rate-limits-and-how-do-i-increase-them
- https://help.mistral.ai/en/articles/455207-can-i-opt-out-of-my-input-or-output-data-being-used-for-training
- Secondary (unverified figures only): docs/free-tier-research/raw/awesome-free-llm-apis/Mistral AI.json
