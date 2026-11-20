---
name: LLMTR
url: "https://llmtr.com"
api_base: "https://llmtr.com/v1"
setup_instructions: |
  1. Register at https://llmtr.com/docs/en/quickstart/ with email verification.
  2. Create an `llmtr-...` key under Dashboard -> API Keys (https://llmtr.com/docs/en/api-keys/).
  3. Point an OpenAI-compatible client at https://llmtr.com/v1 and call POST /chat/completions with a zero-priced model id.
  4. Only rows with `pricing: 0` in GET https://llmtr.com/v1/models are free; the catalog also contains paid, temporary and BYOK-only models.
api_key_url: "https://llmtr.com/docs/en/api-keys/"
---

LLMTR is an OpenAI-compatible gateway with zero-priced models carrying renewable daily quotas. Account + key required. Verified 2026-11-20. **Exact numeric daily quotas are not published.**

**Free Tier:**

- Official model pages describe selected routes as free with a daily usage quota; the quota renews the next day with no published end date.
- Account + email verification + API key required. Official docs do not explicitly state "no card required"; payment is documented only for optional top-ups.
- No numeric RPM/RPD/TPM/TPD is published. Do not infer from observed behavior.

**Free Models:**

Verified zero-priced in live `GET /v1/models` on 2026-11-20:

- `nvidia/nemotron-3-ultra-550b-a55b` — 1M context, text, tools.
- `openai/gpt-oss-safeguard-20b` — 131,072 context, text, tools.
- `qwen/qwen3.8-27b-free` — 131,042 context, text + image, tools.
- `nvidia/nemotron-3.5-super-vl-free` — 1M context, text + image + video, tools.

Catalog tool/vision flags are stale; the live official metadata confirms tools on all four and multimodal input on the last two.

**Limits:**

- No frontmatter numerics: the daily quota exists but its size is unpublished.
- Older model ids can retire with `410 model_retired`.

**Notes:**

- Only `pricing: 0` rows are free. Many ids are paid, temporary, or BYOK-only.
- Exact no-payment quota size and card requirements remain unverified.

**Sources**

- https://llmtr.com/docs/en/quickstart/
- https://llmtr.com/docs/en/api-keys/
- https://llmtr.com/v1/models
- https://llmtr.com/llms-full.txt
- https://llmtr.com/en/models/qwen/qwen3.8-27b-free
- docs/free-tier-research/raw/freellmapi-catalog/platforms/llmtr.json (discovery lead, verified 2026-11-20)
