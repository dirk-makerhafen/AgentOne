---
name: Hugging Face
url: "https://huggingface.co"
setup_instructions: |
  1. Create a free account at https://huggingface.co/join.
  2. Open https://huggingface.co/settings/tokens and create a fine-grained token with "Make calls to Inference Providers" permission.
  3. Export it (`export HF_TOKEN=<token>`) and call `https://router.huggingface.co/v1` (OpenAI-compatible) or use `InferenceClient`.
api_key_url: "https://huggingface.co/settings/tokens"
limits: {}
---

Hugging Face Inference Providers is a unified gateway routing requests to 200+ models across third-party providers with pass-through billing and a small recurring monthly credit.

**Free Tier:**

- Permanent monthly credits (official): Free users $0.10/mo (subject to change, Inference Providers only); PRO $2.00; Team/Enterprise $2.00/seat (general compute credits).
- No markup over provider rates; extra usage requires purchasing credits; legacy serverless API is now the `hf-inference` provider option billed by compute time.

**Free Models:**

- Representative, verify live (any routed model draws from the same $0.10 pool at pass-through rates; 200+ across Cerebras, Groq, Together, Fireworks, Replicate, Cohere, and others): `meta-llama/Llama-3.1-8B-Instruct`, `google/gemma-3-4b-it`, `microsoft/phi-4`, `Qwen/Qwen2.5-7B-Instruct` — routing suffixes `:fastest` (default) / `:cheapest` / `:preferred` / `:<provider>`.

**Limits:**

- Credit-metered; no official RPM/RPD/TPM published — frontmatter `limits` intentionally left empty.
- Secondary reports (unverified): legacy serverless free ≈ a few hundred requests/hour, models ≲10B params, cold starts on unpopular models; PRO adds ~2M monthly Provider credits.

**Notes:**

- Account required; token required; no credit card for free start (card needed for credit purchases/PRO); phone verification unknown.
- Credits apply only to HF-routed requests; bring-your-own provider-key requests are billed by the provider with no HF credits.
- No routed model is $0: e.g. `zai-org/GLM-4.7-Flash` is paid per token (Novita $0.07 in / $0.40 out, DeepInfra $0.06 / $0.40) — discovery-fixture cost-0 rows for it are artifacts; it only draws from the same monthly credit pool.
- Usage visible at `huggingface.co/settings/inference-providers/overview`; org billing via `X-HF-Bill-To` / `bill_to`.

**Sources**

- https://huggingface.co/docs/inference-providers/en/index
- https://huggingface.co/docs/inference-providers/pricing
- Secondary: https://klymentiev.com/blog/huggingface-inference-api (2026-06-10)
