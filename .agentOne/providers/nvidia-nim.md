---
name: NVIDIA NIM
url: "https://build.nvidia.com"
api_base: "https://integrate.api.nvidia.com/v1"
setup_instructions: |
  1. Join the NVIDIA Developer Program (free NVIDIA account).
  2. Sign in at https://build.nvidia.com/explore/discover and pick a model.
  3. Generate an API key at https://build.nvidia.com/settings ("Get API Key").
  4. Call `https://integrate.api.nvidia.com/v1` with `Authorization: Bearer $NVIDIA_API_KEY` and OpenAI-compatible requests.
api_key_url: "https://build.nvidia.com/settings"
limits: {}
---

NVIDIA NIM hosted endpoints on build.nvidia.com provide free prototyping access to dozens of models for Developer Program members, with production served separately under an AI Enterprise license.

**Free Tier:**

- Free hosted access for prototyping/development/testing/research via Developer Program membership; not for production use. Official integrations page (re-verified 2026-09-05): "All models offer a free trial tier with no credit card required."
- No public per-token price for hosted calls; production pricing is per GPU (AI Enterprise from ~$4,500/GPU/year), with a free 90-day evaluation license.

**Free Models:**

- Representative, verify exact slugs live (catalog churns; 50+ hosted from NVIDIA, Meta, Mistral, Microsoft, DeepSeek, Qwen): Nemotron 3 family (see [nemotron-3-nano-30b-a3b](../models/nemotron-3-nano-30b-a3b.md) card — confirm exact hosted slug), `meta/llama-3.3-70b-instruct`, DeepSeek-V4 variants (see [deepseek-v4-flash](../models/deepseek-v4-flash.md) / [deepseek-v4-pro](../models/deepseek-v4-pro.md) cards — confirm exact hosted slug), [`openai/gpt-oss-120b`](../models/gpt-oss-120b.md) — confirm exact slug at build.nvidia.com before use.

**Limits:**

- No published SLA and no documented static numerics — frontmatter `limits` intentionally left empty.
- Community-acknowledged baseline referenced by NVIDIA staff (secondary, unverified as a guarantee): ~40 RPM, varying by model and overall traffic; per-account ceiling shown in the build.nvidia.com usage panel. No self-service increase on the free tier.
- Old 2024 credit model (1,000 signup credits, up to 5,000) is superseded — current regime is rate-limit-governed.

**Notes:**

- NVIDIA account + Developer Program membership required; API key required; no credit card for the hosted trial (official). Phone requirement: unverified in official docs.
- Free tier is development/test only — serving real end users or business transactions requires an AI Enterprise license.
- Downloadable NIM containers are free for dev/test on up to 16 GPUs (you pay the GPU infrastructure).
- Free API access still offered as of 2026-09-05 — file kept.

**Sources**

- https://build.nvidia.com/settings/integrations
- https://developer.nvidia.com/nim
- https://build.nvidia.com
- https://docs.api.nvidia.com/nim/docs/product (NIM FAQ)
- https://forums.developer.nvidia.com/t/api-rate-limit-increase-is-not-granted-by-requesting-it-here/368420 (staff rate-limit statement, 2026-04-29)
