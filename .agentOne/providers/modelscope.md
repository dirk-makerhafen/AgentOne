---
name: ModelScope
url: "https://modelscope.cn"
api_base: "https://api-inference.modelscope.cn/v1"
setup_instructions: |
  1. Register at https://modelscope.cn (Alibaba account or phone) and bind an Alibaba Cloud account; complete real-name verification.
  2. Create an access token at My → AccessToken (https://modelscope.cn/my/myaccesstoken).
  3. Call https://api-inference.modelscope.cn/v1 with the token as the API key and the ModelScope Model-ID as `model`, using any OpenAI-compatible client.
api_key_url: "https://modelscope.cn/my/myaccesstoken"
limits:
  requests:
    day: 2000
---

ModelScope (Alibaba 魔搭) is a CN-hosted model hub whose API-Inference serves open-source models free of charge to registered users via OpenAI-compatible, Anthropic-compatible, and Responses interfaces.

**Free Tier:**

- Permanent free API-Inference for registered users — not trial credits. Officially described as a non-commercial, non-profit product with dynamically adjusted quotas and concurrency.

**Free Models:**

- `Qwen/Qwen3.5-35B-A3B` — 256K context (representative, verify live).
- `Qwen/Qwen3.5-27B` — 256K context (representative, verify live).
- Reachable under the free API-Inference quota (discovery-consistent set, confirm each model page): `ZhipuAI/GLM-4.5`, `ZhipuAI/GLM-4.6`, `Qwen/Qwen3-235B-A22B-Instruct-2507`, `Qwen/Qwen3-235B-A22B-Thinking-2507`, `Qwen/Qwen3-30B-A3B-Instruct-2507`, `Qwen/Qwen3-30B-A3B-Thinking-2507`, `Qwen/Qwen3-Coder-30B-A3B-Instruct`.
- Any API-Inference-enabled model ID (Qwen3/Qwen3-VL/Coder series, DeepSeek-V4-Pro/Flash, GLM-4.7-Flash/5.x, MiniMax, Kimi-K2.5, ERNIE-4.5 family reported) — roster is dynamic; confirm API-Inference availability on each model page.
- No model-catalog links added: none of the `models/` cards has a verified ModelScope-side free ID. A secondary (itsfree.ai, 2026) reports MiniMax M3, DeepSeek V4, and GLM as reachable via the free tier — re-verification lead only, not a verified free listing.

**Limits:**

- Free API-Inference quota: 2,000 API calls/day per user, shared across all models, reset daily 00:00 (UTC+8), no carryover; `429` past the limit. Corroborated by three secondaries citing official billing rules (re-checked 2026-09-05); the official intro/limits pages are JS-rendered and could not be directly re-confirmed — re-confirm after signup before relying on the number.
- Per-model daily quotas are dynamically adjusted and capped at 500 (secondary-reported against official docs) — dynamic values, so documented in the body only, not frontmatter.
- Official docs state quotas and concurrency are dynamically adjusted based on resource utilization.

**Notes:**

- Account and access token required; no payment/billing info required.
- Phone verification and Alibaba Cloud account binding plus real-name verification reported required (secondary-sourced; CN registration page not directly verifiable) — overseas and international-Alibaba-Cloud accounts are reported unable to bind (401 "Please bind your Alibaba Cloud account before use"), so overseas users may be unable to sign up.
- CN-hosted; expect high latency outside Asia-Pacific.
- Non-commercial/non-profit framing; commercial-use terms unclear — verify before shipping.
- No credit card required.

**Sources**

- https://modelscope.cn/docs/model-service/API-Inference/intro
- https://modelscope.cn/docs/model-service/API-Inference/limits
- https://github.com/TheMrguiller/Free-LLM-Router/blob/main/docs/tutorials/modelscope.md
- https://freellms.org/providers/modelscope/
- https://itsfree.ai/provider/cloud-modelscope/ (50-model live list, 2,000 req/day)
- https://github.com/nejib1/Free-LLM
