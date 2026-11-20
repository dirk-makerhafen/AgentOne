---
name: Inferbase
url: "https://inferbase.ai"
api_base: "https://api.inferbase.ai/v1"
setup_instructions: |
  1. Register at https://inferbase.ai/register (email/password with verification, or Google) and complete onboarding.
  2. Open Gateway -> API keys and create an `inf_...` key.
  3. Point an OpenAI-compatible client at https://api.inferbase.ai/v1 (the full base is https://api.inferbase.ai/api/v1/inference).
  4. Call a managed model id; see https://api.inferbase.ai/v1/models for the current roster.
api_key_url: "https://inferbase.ai/register"
limits:
  requests:
    minute: 60
    day: 100
    month: 5000
---

Inferbase is an OpenAI-compatible managed-model gateway with a standing $0 Free plan and no card. Account + key required. Verified 2026-11-20.

**Free Tier:**

- $0/month, no time limit, no card.
- 5,000 requests/month on any model and any key.
- 100 managed requests/day plus $0.50 model usage/day (a usage-value cap, not a one-time credit).
- 60 RPM per key and 10 managed requests/minute per organization.
- Managed models up to $2.00 per 1M output tokens; 8,192 input / 1,024 output tokens per managed request.

**Free Models:**

All 38 catalog IDs were confirmed present in the official unauthenticated `GET https://api.inferbase.ai/v1/models`. "Free" is plan-level for managed models within the daily allowance, not a per-model zero-price tag.

- Common limits: 8,192 context (catalog-reported; official plan caps managed requests at 8,192 in / 1,024 out). No per-model RPD/TPM published.
- Tools (`tools`, `tool_choice`, `parallel_tool_calls`) are exposed for 37 of 38 ids in the official API; `qwen2-5-72b-instruct:fp8` is the exception. Catalog marks tools false for all — official API wins.
- Vision is not verified; catalog flags all false and the official model response exposes no image-input parameter (even for `qwen3-vl-*` and `zai-glm-4-*v` ids).
- Verified ids: `deepseek-v4-flash:fp8`, `qwen3-8-flash`, `minimax-m3`, `google-gemma-4-31b-it`, `qwen3-coder-480b-a35b-instruct:turbo`, `deepseek-v4-flash-0731`, `openai-gpt-oss-120b`, `openai-gpt-oss-20b`, `mistral-small-3-2-24b-instruct-2506:fp8`, `google-gemma-3-27b-it`, `google-gemma-4-26b-a4b-it`, `meta-llama-3-3-70b-instruct`, `meta-llama-4-scout-17b-16e-instruct:fp8`, `nvidia-nemotron-3-nano-30b-a3b`, `qwen3-14b:fp8`, `qwen3-5-9b`, `qwen3-6-35b-a3b`, `qwen3-next-80b-a3b-instruct:fp8`, `qwen3-vl-235b-a22b-instruct:fp8`, `qwen3-vl-30b-a3b-instruct:fp8`, `zai-glm-4-5-air`, `zai-glm-4-5v`, `zai-glm-4-6v`, `zai-glm-4-7:fp4`, `zai-glm-4-7-flash`, `deepseek-v3`, `google-gemma-3-12b-it`, `google-gemma-3-4b-it`, `meta-llama-3-1-8b-instruct`, `mistral-nemo-instruct-2407:fp8`, `mistral-small-24b-instruct-2501:fp8`, `qwen2-5-72b-instruct:fp8`, `qwen3-5-35b-a3b`, `zai-glm-4-6:fp4`, `deepseek-v3-1:fp4`, `deepseek-v3-2:fp4`, `qwen3-32b:fp8`, `qwen3-30b-a3b:fp8`.

**Limits:**

- Frontmatter records the standing request caps. The $0.50/day usage value and $2.00/1M output ceiling are plan rules, not token counts, so they are documented in the body only.

**Notes:**

- The allowance is shared across the account, not per model.
- FP8/Turbo suffixes are explicit model ids, not interchangeable aliases.
- Authenticated inference and actual free deduction behavior were not live-tested.

**Sources**

- https://inferbase.ai/pricing
- https://inferbase.ai/docs
- https://inferbase.ai/docs/api
- https://inferbase.ai/docs/getting-started/quickstart
- https://inferbase.ai/docs/gateway/api-keys
- https://api.inferbase.ai/v1/models
- docs/free-tier-research/raw/freellmapi-catalog/platforms/inferbase.json (discovery lead, verified 2026-11-20)
