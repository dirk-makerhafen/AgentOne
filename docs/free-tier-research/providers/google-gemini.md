---
name: Google AI Studio
url: "https://aistudio.google.com"
setup_instructions: |
  1. Sign in to https://aistudio.google.com with a Google account.
  2. Open https://aistudio.google.com/app/apikey and create an API key ("Get API key" / "Create API key").
  3. Call the Gemini API with that key (free tier applies automatically, no billing account needed).
  4. Optional: link a Cloud billing account ("Set up Billing") to move the project to paid Tier 1.
api_key_url: "https://aistudio.google.com/app/apikey"
limits: {}
---

Google AI Studio is Google's developer console for the Gemini Developer API, offering a permanent free tier with per-project rate limits.

**Free Tier:**

- Permanent free tier, no credit card, no expiration — "Free of charge" input/output pricing rows for Flash / Flash-Lite models on the official pricing page (verified 2026-09-05).
- Paid Tier 1/2/3 unlock by linking a Cloud billing account; Tier 1 has no minimum spend.

**Free Models:**

- Confirmed free of charge on the official pricing page (verified 2026-09-05): `gemini-2.5-flash`, `gemini-2.5-flash-lite` — 1M-token context window, 65K max output.
- Also listed on the official models page; free status verify live per model: `gemini-2.0-flash`, `gemini-2.0-flash-lite`, `gemini-3.5-flash`, `gemini-3.5-flash-lite` (discovery-reported IDs `gemini-3.6-flash`, `gemini-3.7-flash`, `gemini-3.1-flash-lite` are unverified — confirm live).
- `gemini-2.5-pro`: pricing-page tables show "Not available" free-tier rows for some Pro pricing dimensions; secondary sources report a small free RPD allowance (25–100 RPD, conflicting) — treat Pro free access as unverified, check `aistudio.google.com/rate-limit` before building on it.
- None of the 9 catalogued model cards (`deepseek-v4-flash`, `glm-4.5-flash`, etc.) is served through this provider — no model-card links apply.

**Limits:**

- Official dimensions: requests per minute (RPM), tokens per minute (TPM), requests per day (RPD); evaluated against all three, 429 on any breach; applied per project (not per key); RPD resets at midnight Pacific.
- No static per-model figures are published on the open docs page — live values only behind login at `aistudio.google.com/rate-limit`, so frontmatter `limits` is intentionally left empty (never derive/guess).
- Secondary snapshots (unverified, volatile — Google cut quotas Dec 2025, figures conflict across sources): Flash ~10–15 RPM / ~250K–1M TPM / ~250–1,500 RPD; Flash-Lite ~30 RPM / ~1M TPM / ~1,000–1,500 RPD; Pro ~5 RPM / ~250K–1M TPM / ~25–100 RPD. Always live-verify before building.
- Grounding extras (official pricing page, verified 2026-09-05): Google Search grounding free up to 500 RPD shared across Flash/Flash-Lite on the free tier; Google Maps grounding 500 RPD.

**Notes:**

- Endpoint: `https://generativelanguage.googleapis.com/v1beta` (native REST; OpenAI-compatible path also documented — verify exact path in the official quickstart before use).
- Account required (Google account); API key required; no credit card for free; phone verification unknown.
- Free-tier prompts and responses may be used by Google to improve products (see ai.google.dev/gemini-api/terms); paid tiers carry a no-training-use commitment.
- Vertex AI is a separate access path with different project-level quotas.

**Sources**

- https://ai.google.dev/gemini-api/docs/models (model IDs, context/output limits — verified 2026-09-05)
- https://ai.google.dev/gemini-api/docs/pricing (free-of-charge Flash/Flash-Lite rows, grounding RPD — verified 2026-09-05)
- https://ai.google.dev/gemini-api/docs/rate-limits (RPM/TPM/RPD dimensions, per-project enforcement)
- https://ai.google.dev/gemini-api/docs/billing
- https://aistudio.google.com/rate-limit (live per-project limits)
- Secondary snapshots (unverified numerics only): https://aipromptshub.co/blog/gemini-api-free-tier-rate-limits (2026-06-27), https://www.aifreeapi.com/en/posts/gemini-api-free-tier-rate-limits (2026-01-27)
- Discovery lead (not authoritative): docs/free-tier-research/raw/awesome-free-llm-apis/Google Gemini.json
