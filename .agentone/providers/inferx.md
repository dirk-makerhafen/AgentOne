---
name: InferX
url: "https://www.inferx.net"
api_base: "https://model.inferx.net/v1"
setup_instructions: |
  1. Sign in at https://model.inferx.net/login and open an endpoint.
  2. Copy the API Base URL, Model Name, and API Key from the Console Client Setup panel (production URLs can be tenant/endpoint-specific — use the exact Console values).
  3. Install the OpenAI client (`pip install openai`) and point it at the base URL (default `https://model.inferx.net/v1`) with the key as Bearer token; pass the Model Name as `model`.
  4. Re-verify the endpoint-pricing page before use — free models are rotating promotions.
api_key_url: "https://model.inferx.net/login"
limits: {}
---

InferX (InferX AI, San Francisco) is a serverless inference provider with an "InferX Free" $0/mo tier: free promotional models on enterprise GPUs behind an OpenAI-compatible API with zero data retention.

**Free Tier:**

- InferX Free: $0/mo, free models available, OpenAI-compatible API, zero data retention.
- Free models are promotions ("Free · 100% off / 100% discount") and rotate — re-verify the endpoint-pricing page before use.
- Paid path is prepaid pay-as-you-go usage credits; no subscription required for free models.

**Free Models:**

- `qwen38-flash-next` (Qwen3.8 Flash-Next) — $0 in / $0 out (endpoint `qwen38-flash-next?tenant=public`; confirm Model Name in console).
- `Qwen3.6-27B-FP8` (Qwen3.6 27B) — $0 in / out / cached, 262,144 context (confirm Model Name in console); see [Qwen3.6-27B card](../models/qwen3.6-27b.md).
- `Qwen3.6-35B-A3B-FP8` (Qwen3.6 35B A3B) — $0 in / out / cached, 262,000 context (confirm Model Name in console); see [Qwen3.6-35B-A3B card](../models/qwen3.6-35b-a3b.md).
- `gemma-4-31B-it-fp8` (Gemma 4 31B IT FP8) — $0 in / out / cached, 262,144 context; see [gemma-4-31b-it](../models/gemma-4-31b-it.md) (confirm Model Name in console).
- [`gpt-oss-20b`](../models/gpt-oss-20b.md) (GPT-OSS 20B) — $0 in / out / cached, 20,000 context (confirm Model Name in console).
- NOT free (do not list as free): `Qwen3.8-27B-FP8` (96% off, paid), `deepseek-v4-flash-0731` (70% off, paid), `Qwen3-Coder-Next-FP8` (paid, $0.18 in / $0.90 out) — despite discovery-fixture cost-0 rows.

**Limits:**

- No numeric rate limits are published. The official API reference states rate-limit tiers remain withheld pending verification — frontmatter limits omitted deliberately.
- Expect `429`s under load; promotions rotate.

**Notes:**

- Account and API key required; no subscription for free models. Whether a credit card is required for the free tier is unconfirmed on official pages (only third-party guides claim no card) — do not assert either way.
- Endpoint `https://model.inferx.net/v1` is the quickstart default and matches the discovery fixture; use the exact base URL from the Console.
- Discovery fixtures also list `qwen/qwen3.5-122b-a10b-nvfp4` at cost 0, but it does not appear on the official pricing page — excluded; the console catalog is the source of truth.
- Model bullets above carry catalog display names plus endpoint slugs; literal `model` strings are tenant-specific — always copy the Model Name from the Console Client Setup panel.

**Sources**

- https://inferx.net/pricing/endpoints (endpoint pricing with $0 rows for the 5 free models, verified 2026-09-05)
- https://www.inferx.net/pricing (InferX Free $0/mo terms, verified 2026-09-05)
- https://www.inferx.net/models (free flags + contexts for Qwen3.6 pair, verified 2026-09-05)
- https://inferx.net/docs/quickstart
- https://inferx.net/docs/api-reference (rate-limit tiers withheld, verified 2026-09-05)
