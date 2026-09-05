---
name: Google AI Studio
url: "https://aistudio.google.com"
setup_instructions: |
  1. Sign in to https://aistudio.google.com with a Google account.
  2. Open https://aistudio.google.com/app/apikey and create an API key.
  3. Call the Gemini API with that key (free tier applies automatically).
  4. Optional: link a Cloud billing account ("Set up Billing") to move the project to paid Tier 1.
api_key_url: "https://aistudio.google.com/app/apikey"
limits: {}
---

Google AI Studio is Google's developer console for the Gemini Developer API, offering a permanent free tier with per-project rate limits.

**Free Tier:**

- Permanent free tier, no credit card, no expiration — "Free input & output tokens" for limited models.
- Paid Tier 1/2/3 unlock by linking a Cloud billing account; Tier 1 has no minimum spend.

**Free Models:**

- Representative families, verify live (exact IDs rotate; official list is per-account at `aistudio.google.com/rate-limit`): Gemini 2.5 Pro, Gemini 2.5 Flash / Flash-Lite, Gemini 2.0 Flash / Flash-Lite, Gemini 3.x Flash previews — 1M-token context window.

**Limits:**

- Official dimensions: requests per minute (RPM), input tokens per minute (TPM), requests per day (RPD); evaluated against all three, 429 on any breach; applied per project (not per key); RPD resets at midnight Pacific.
- No static per-model figures are published on the open docs page — live values only behind login. Secondary snapshots (unverified, volatile — Google cut quotas Dec 2025): Flash ~10–15 RPM / ~250K–1M TPM / ~250–1,500 RPD; Flash-Lite up to ~30 RPM / ~1M TPM / ~1,000–1,500 RPD; Pro ~5 RPM / ~250K TPM / ~25–100 RPD. Always live-verify before building.

**Notes:**

- Account required (Google account); API key required; no credit card for free; phone verification unknown.
- Free-tier prompts and responses may be used by Google to improve products (see ai.google.dev/gemini-api/terms); paid tiers carry a no-training-use commitment.
- Vertex AI is a separate access path with different project-level quotas.

**Sources**

- https://ai.google.dev/gemini-api/docs/rate-limits
- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/docs/billing
- https://aistudio.google.com/rate-limit (live per-project limits)
- Secondary snapshots: https://aipromptshub.co/blog/gemini-api-free-tier-rate-limits (2026-06-27), https://www.aifreeapi.com/en/posts/gemini-api-free-tier-complete-guide (2026-03-17)
