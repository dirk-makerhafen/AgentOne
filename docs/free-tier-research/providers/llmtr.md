---
name: LLMTR
url: https://llmtr.com
api_base: https://llmtr.com/v1
setup_instructions: '1. Register at https://llmtr.com/docs/en/quickstart/ with email
  verification.

  2. Create an `llmtr-...` key under Dashboard -> API Keys (https://llmtr.com/docs/en/api-keys/).

  3. Point an OpenAI-compatible client at https://llmtr.com/v1 and call POST /chat/completions
  with a zero-priced model id.

  4. Only rows with `pricing: 0` in GET https://llmtr.com/v1/models are free; the
  catalog also contains paid, temporary and BYOK-only models.

  '
api_key_url: https://llmtr.com/docs/en/api-keys/
---

LLMTR is an OpenAI-compatible gateway with zero-priced models carrying renewable daily quotas. Account + key required. Verified 2026-11-20. **Exact numeric daily quotas are not published.**

**Sources**

- https://llmtr.com/docs/en/quickstart/
- https://llmtr.com/docs/en/api-keys/
- https://llmtr.com/v1/models
- https://llmtr.com/llms-full.txt
- https://llmtr.com/en/models/qwen/qwen3.8-27b-free
- docs/free-tier-research/raw/freellmapi-catalog/platforms/llmtr.json (discovery lead, verified 2026-11-20)
