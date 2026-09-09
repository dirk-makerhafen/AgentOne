---
name: Hugging Face
url: "https://huggingface.co"
api_base: "https://router.huggingface.co/v1"
setup_instructions: |
  1. Create a free account at https://huggingface.co/join.
  2. Open https://huggingface.co/settings/tokens and create a fine-grained token with "Make calls to Inference Providers" permission.
  3. Export it (`export HF_TOKEN=<token>`) and call `https://router.huggingface.co/v1` (OpenAI-compatible) or use `InferenceClient`.
api_key_url: "https://huggingface.co/settings/tokens"
limits: {}
---

Hugging Face Inference Providers is a unified gateway routing requests to 200+ models across third-party providers with pass-through billing and a small recurring monthly credit.

**Free Tier:**

- Permanent monthly credits (official pricing page, verified 2026-09-05): Free users $0.10/mo (subject to change, Inference Providers only); PRO $2.00; Team/Enterprise $2.00/seat (general compute credits, shared per org).
- No markup over provider rates; extra usage requires purchasing credits; monthly credits apply automatically to routed requests before any pay-as-you-go billing.

**Free Models:**

- Representative, verify live (any routed model draws from the same $0.10 pool at pass-through rates; 200+ across Cerebras, Groq, Together, Fireworks, Replicate, Novita, DeepInfra, Cohere, Z.ai and others): [openai/gpt-oss-120b](../models/gpt-oss-120b.md) (used in the official quickstart — verified 2026-09-05), `meta-llama/Llama-3.1-8B-Instruct`, `google/gemma-3-4b-it`, `microsoft/phi-4`, `Qwen/Qwen2.5-7B-Instruct` — routing suffixes `:fastest` (default) / `:cheapest` / `:preferred` / `:<provider>`.
- No routed model is $0: e.g. `zai-org/GLM-4.7-Flash` is paid per token — discovery-fixture cost-0 rows for it are artifacts; it only draws from the same monthly credit pool.

**Limits:**

- Credit-metered; no official RPM/RPD/TPM published — frontmatter `limits` intentionally left empty.
- Secondary reports (unverified): legacy serverless free ≈ a few hundred requests/hour, models ≲10B params, cold starts on unpopular models; PRO adds ~$2.00 monthly credits.

**Notes:**

- Account required; token required; no credit card for free start (card needed for credit purchases/PRO); phone verification unknown.
- Endpoint (verified 2026-09-05): `https://router.huggingface.co/v1` (OpenAI-compatible, chat completions only) — `POST /v1/chat/completions`, `GET /v1/models`; `InferenceClient` covers all task types with client-side provider selection.
- Credits apply only to HF-routed requests; bring-your-own provider-key requests are billed by the provider with no HF credits.
- Usage visible at `huggingface.co/settings/inference-providers/overview` and the billing page; org billing via explicit bill-to selection.

**Sources**

- https://huggingface.co/docs/inference-providers/en/index (router endpoint, token permission, provider suffixes — verified 2026-09-05)
- https://huggingface.co/docs/inference-providers/pricing ($0.10 / $2.00 / $2.00-seat credits, pass-through billing — verified 2026-09-05)
- Discovery lead (not authoritative): docs/free-tier-research/raw/awesome-free-llm-apis/Hugging Face.json
