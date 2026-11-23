---
name: Hugging Face
url: https://huggingface.co
api_base: https://router.huggingface.co/v1
setup_instructions: '1. Create a free account at https://huggingface.co/join.

  2. Open https://huggingface.co/settings/tokens and create a fine-grained token with
  "Make calls to Inference Providers" permission.

  3. Export it (`export HF_TOKEN=<token>`) and call `https://router.huggingface.co/v1`
  (OpenAI-compatible) or use `InferenceClient`.

  '
api_key_url: https://huggingface.co/settings/tokens
---

Hugging Face Inference Providers is a unified gateway routing requests to 200+ models across third-party providers with pass-through billing and a small recurring monthly credit.

**Sources**

- https://huggingface.co/docs/inference-providers/en/index (router endpoint, token permission, provider suffixes — verified 2026-09-05)
- https://huggingface.co/docs/inference-providers/pricing ($0.10 / $2.00 / $2.00-seat credits, pass-through billing — verified 2026-09-05)
- Discovery lead (not authoritative): docs/free-tier-research/raw/awesome-free-llm-apis/Hugging Face.json
