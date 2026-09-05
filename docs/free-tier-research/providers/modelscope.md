---
name: ModelScope
url: "https://modelscope.cn"
setup_instructions: |
  1. Register at https://modelscope.cn (Alibaba account or phone) and complete real-name verification (Alibaba Cloud account binding reported required).
  2. Create an access token at My → AccessToken (https://modelscope.cn/my/myaccesstoken).
  3. Call https://api-inference.modelscope.cn/v1 with the token as the API key and the ModelScope Model-ID as `model`, using any OpenAI-compatible client.
api_key_url: "https://modelscope.cn/my/myaccesstoken"
limits:
---

ModelScope (Alibaba 魔搭) is a CN-hosted model hub whose API-Inference serves open-source models free of charge to registered users via OpenAI-compatible, Anthropic-compatible, and Responses interfaces.

**Free Tier:**

- Permanent free API-Inference for registered users — not trial credits. Officially described as a non-commercial, non-profit product with dynamically adjusted quotas and concurrency.

**Free Models:**

- `Qwen/Qwen3.5-35B-A3B` — 256K context (representative, verify live).
- `Qwen/Qwen3.5-27B` — 256K context (representative, verify live).
- Reachable under the free API-Inference quota (discovery-consistent set, confirm each model page): `ZhipuAI/GLM-4.5`, `ZhipuAI/GLM-4.6`, `Qwen/Qwen3-235B-A22B-Instruct-2507`, `Qwen/Qwen3-235B-A22B-Thinking-2507`, `Qwen/Qwen3-30B-A3B-Instruct-2507`, `Qwen/Qwen3-30B-A3B-Thinking-2507`, `Qwen/Qwen3-Coder-30B-A3B-Instruct`.
- Any API-Inference-enabled model ID (Qwen3/Qwen3-VL/Coder series, DeepSeek-V4-Pro/Flash, GLM-4.7-Flash/5.x, MiniMax, Kimi-K2.5, ERNIE-4.5 family reported) — roster is dynamic; confirm API-Inference availability on each model page.

**Limits:**

- Free API-Inference quota: 2,000 API calls/day per user, shared across all models, reset daily 00:00 (UTC+8), no carryover; `429` past the limit. Corroborated by three secondaries citing official billing rules; the official intro/limits pages are JS-rendered and could not be directly re-confirmed — re-confirm after signup before relying on the number.
- Official docs state quotas and concurrency are dynamically adjusted based on resource utilization.

**Notes:**

- Account and access token required; no payment/billing info required.
- Phone verification and Alibaba Cloud account binding plus real-name verification reported required (secondary-sourced; CN registration page not directly verifiable) — overseas users may be unable to sign up.
- CN-hosted; expect high latency outside Asia-Pacific.
- Non-commercial/non-profit framing; commercial-use terms unclear — verify before shipping.
- No credit card required.

**Sources**

- https://modelscope.cn/docs/model-service/API-Inference/intro
- https://modelscope.ai/docs/model-service/API-Inference/limits
- https://github.com/TheMrguiller/Free-LLM-Router/blob/main/docs/tutorials/modelscope.md
- https://freellms.org/providers/modelscope/
- https://github.com/nejib1/Free-LLM
