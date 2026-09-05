---
name: InferX
url: "https://www.inferx.net"
setup_instructions: |
  1. Sign in at https://model.inferx.net/login and open an endpoint.
  2. Copy the API Base URL, Model Name, and API Key from the Console Client Setup panel (production URLs can be tenant/endpoint-specific — use the exact Console values).
  3. Install the OpenAI client (`pip install openai`) and point it at the base URL (default `https://model.inferx.net/v1`) with the key as Bearer token; pass the Model Name as `model`.
api_key_url: "https://model.inferx.net/login"
limits:
---

InferX (InferX AI, San Francisco) is a serverless inference provider with an "InferX Free" $0/mo tier: free promotional models on enterprise GPUs behind an OpenAI-compatible API with zero data retention.

**Free Tier:**

- InferX Free: $0/mo, free models available, OpenAI-compatible API, zero data retention.
- Free models are promotions ("Free · 100% off") and rotate — re-verify the endpoint-pricing page before use.
- Paid path is prepaid pay-as-you-go usage credits; no subscription required for free models.

**Free Models:**

- `qwen38-flash-next` (Qwen3.8 Flash-Next) — $0 in / $0 out (catalog-reported ID, confirm in console).
- `Qwen3.6-27B-FP8` — $0 in / out / cached, 262,144 context (catalog-reported ID, confirm in console).
- `Qwen3.6-35B-A3B-FP8` — $0 in / out / cached, 262,000 context (catalog-reported ID, confirm in console).
- `gemma-4-31B-it-fp8` (Gemma 4 31B IT FP8) — $0 in / out / cached, 262,144 context; see [model card](../models/gemma-4-31b-it.md) (catalog-reported ID, confirm in console).
- `gpt-oss-20b` (GPT-OSS 20B) — $0 in / out / cached, 20,000 context (catalog-reported ID, confirm in console).
- NOT free: `Qwen3-Coder-Next-FP8` is paid ($0.18 in / $0.90 out) — do not list it as free despite discovery-fixture cost-0 rows.

**Limits:**

- No numeric rate limits are published. The official API reference states rate-limit tiers remain withheld pending verification — frontmatter limits omitted deliberately.
- Expect `429`s under load; promotions rotate.

**Notes:**

- Account and API key required; no subscription for free models. Whether a credit card is required for the free tier is unconfirmed on official pages (only third-party guides claim no card) — do not assert either way.
- Endpoint `https://model.inferx.net/v1` is the quickstart default; use the exact base URL from the Console.
- Discovery fixtures also list `qwen/qwen3.5-122b-a10b-nvfp4` at cost 0, but it does not appear on the official pricing page — excluded; the console catalog is the source of truth.

**Sources**

- https://inferx.net/pricing/endpoints (endpoint pricing with $0 rows, verified 2026-09-05)
- https://www.inferx.net/pricing
- https://inferx.net/docs/quickstart
- https://inferx.net/docs/api-reference
