---
name: Google AI Studio
url: https://aistudio.google.com
api_base: https://generativelanguage.googleapis.com/v1beta
litellm_prefix: gemini
setup_instructions: '1. Sign in to https://aistudio.google.com with a Google account.

  2. Open https://aistudio.google.com/app/apikey and create an API key ("Get API key"
  / "Create API key").

  3. Call the Gemini API with that key (free tier applies automatically, no billing
  account needed).

  4. Optional: link a Cloud billing account ("Set up Billing") to move the project
  to paid Tier 1.

  '
api_key_url: https://aistudio.google.com/app/apikey
---

Google AI Studio is Google's developer console for the Gemini Developer API, offering a permanent free tier with per-project rate limits.

**Sources**

- https://ai.google.dev/gemini-api/docs/models (model IDs, context/output limits — verified 2026-09-05)
- https://ai.google.dev/gemini-api/docs/pricing (free-of-charge Flash/Flash-Lite rows, grounding RPD — verified 2026-09-05)
- https://ai.google.dev/gemini-api/docs/rate-limits (RPM/TPM/RPD dimensions, per-project enforcement)
- https://ai.google.dev/gemini-api/docs/billing
- https://aistudio.google.com/rate-limit (live per-project limits)
- Secondary snapshots (unverified numerics only): https://aipromptshub.co/blog/gemini-api-free-tier-rate-limits (2026-06-27), https://www.aifreeapi.com/en/posts/gemini-api-free-tier-rate-limits (2026-01-27)
- Discovery lead (not authoritative): docs/free-tier-research/raw/awesome-free-llm-apis/Google Gemini.json
