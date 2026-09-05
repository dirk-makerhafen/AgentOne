---
name: NVIDIA NIM
url: "https://build.nvidia.com"
setup_instructions: |
  1. Join the NVIDIA Developer Program (free NVIDIA account).
  2. Sign in at https://build.nvidia.com/explore/discover and pick a model.
  3. Generate an API key from the model page ("Generate API key").
  4. Call `https://integrate.api.nvidia.com/v1` with OpenAI-compatible requests.
api_key_url: "https://build.nvidia.com/explore/discover"
limits: {}
---

NVIDIA NIM hosted endpoints on build.nvidia.com provide free prototyping access to dozens of models for Developer Program members, with production served separately under an AI Enterprise license.

**Free Tier:**

- Free hosted access for prototyping/development/testing/research via Developer Program membership; not for production use.
- No public per-token price for hosted calls; production pricing is per GPU (AI Enterprise from ~$4,500/GPU/year), with a free 90-day evaluation license.

**Free Models:**

- Representative, verify live (catalog slugs churn; 50+ hosted from NVIDIA, Meta, Mistral, Microsoft, DeepSeek, Qwen): Nemotron 3 family, `meta/llama-3.3-70b-instruct`, DeepSeek-V4 variants, [`openai/gpt-oss-120b`](../models/gpt-oss-120b.md) — confirm exact slug at build.nvidia.com before use.

**Limits:**

- No published SLA. Community-acknowledged baseline referenced by NVIDIA staff (secondary, unverified as a guarantee): ~40 RPM, varying by model and overall traffic; per-account ceiling shown in the build.nvidia.com usage panel.
- Old 2024 credit model (1,000 signup credits, up to 5,000) is superseded — current regime is rate-limit-governed with no self-service increase on the free tier.
- Frontmatter `limits` intentionally left empty: no verified static official figures exist.

**Notes:**

- NVIDIA account + Developer Program membership required; API key required; credit card and phone requirements unknown per official docs (guides report no credit card for hosted trial).
- Free tier is development/test only — serving real end users or business transactions requires an AI Enterprise license.
- Downloadable NIM containers are free for dev/test on up to 16 GPUs (you pay the GPU infrastructure).

**Sources**

- https://developer.nvidia.com/nim
- https://build.nvidia.com
- https://docs.api.nvidia.com/nim/docs/product (NIM FAQ)
- https://forums.developer.nvidia.com (API credit / rate-limit staff threads)
- Secondary: https://decodethefuture.org/en/nvidia-nim-api-pricing-limits-guide/ (2026-05-16)
