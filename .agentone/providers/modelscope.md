---
name: ModelScope
url: "https://modelscope.cn"
api_base: "https://api-inference.modelscope.cn/v1"
setup_instructions: |
  1. Create an Alibaba Cloud account and complete real-name verification.
  2. Sign up at https://modelscope.cn and bind your Alibaba Cloud account.
  3. Create an access token at https://modelscope.cn/my/myaccesstoken.
  4. Call the OpenAI-compatible endpoint at https://api-inference.modelscope.cn/v1 with the token as Bearer token.
api_key_url: "https://modelscope.cn/my/myaccesstoken"
limits:
  requests:
    day: 2000
---

ModelScope provides free API-Inference for registered users with Alibaba Cloud real-name verification. Dynamic quotas and concurrency limits apply.

**Free Tier:**

- Free API-Inference for registered users (Alibaba Cloud account + real-name verification required).
- 2,000 RPD total; ≤500 RPD/model (dynamic quotas + dynamic concurrency).

**Free Models (verified 2026-09-05):**

- `Qwen/Qwen3.5-35B-A3B` — 256K context.
- `Qwen/Qwen3.5-27B` — 256K context.
- Additional API-Inference-enabled models (live catalog at `/v1/models`; quotas vary).

**Limits:**

- 2,000 RPD total; ≤500 RPD per model (dynamic).
- Dynamic concurrency limits.
- 429 when quota exhausted.

**Notes:**

- Account required; API key required; Alibaba Cloud real-name verification required.
- OpenAI-compatible: `https://api-inference.modelscope.cn/v1`.
- No model-card links currently catalogued for these specific variants.

**Sources**

- https://modelscope.cn (official site)
- https://modelscope.cn/my/myaccesstoken (token creation)
- https://api-inference.modelscope.cn/v1/models (live model list)
- docs/free-tier-research/raw/awesome-free-llm-apis/ModelScope.json (discovery snapshot, verified 2026-09-05)