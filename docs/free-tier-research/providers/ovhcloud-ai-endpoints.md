---
name: OVHcloud AI Endpoints
url: "https://www.ovhcloud.com/en/public-cloud/ai-endpoints/"
api_base: "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1"
setup_instructions: |
  1. No account or API key required for anonymous free tier (2 RPM per IP per model).
  2. Call the OpenAI-compatible endpoint directly at https://oai.endpoints.kepler.ai.cloud.ovh.net/v1.
  3. Optional: create an OVHcloud account for higher limits and persistent access.
api_key_url: "https://www.ovhcloud.com/en/public-cloud/ai-endpoints/catalog/"
limits:
  requests:
    minute: 2
---

OVHcloud AI Endpoints provides a free anonymous tier (no API key, no signup) with 2 RPM per IP per model. 20+ open-weight models hosted in EU.

**Free Tier:**

- Permanent free anonymous tier (no API key, no signup, no credit card).
- 2 RPM per IP per model.
- Models hosted in EU (GDPR-friendly).

**Free Models (verified 2026-09-05):**

- `Qwen3.5-397B-A17B` — 262K context, ~32K max output, text + vision.
- `gpt-oss-120b` — 131K context, ~32K max output, text.
- `gpt-oss-20b` — 131K context, ~8K max output, text.
- `Meta-Llama-3_3-70B-Instruct` — 131K context, ~4K max output, text.
- `Qwen3.8-27B` — 262K context, text + vision.
- `Qwen3.6-27B` — 262K context, ~32K max output, text + vision.
- `Qwen3.5-9B` — 262K context, ~8K max output, text + vision.
- `Qwen2.5-VL-72B-Instruct` — 32K context, ~8K max output, text + vision.
- `Mistral-Small-3.2-24B-Instruct-2506` — 128K context, ~4K max output, text + vision.
- `Mistral-Nemo-Instruct-2407` — 118K context, ~4K max output, text.

**Limits:**

- 2 RPM per IP per model (anonymous tier).
- 429 when rate limit exceeded.
- Optional OVHcloud account for higher limits.

**Notes:**

- No account required for anonymous tier; no API key; no credit card.
- OpenAI-compatible: `https://oai.endpoints.kepler.ai.cloud.ovh.net/v1`.
- EU-hosted models (data residency).
- Model IDs use simple names (no provider/ prefix).

**Sources**

- https://www.ovhcloud.com/en/public-cloud/ai-endpoints/ (official site)
- https://www.ovhcloud.com/en/public-cloud/ai-endpoints/catalog/ (model catalog)
- https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/models (live model list)
- docs/free-tier-research/raw/awesome-free-llm-apis/OVHcloud AI Endpoints.json (discovery snapshot, verified 2026-09-05)