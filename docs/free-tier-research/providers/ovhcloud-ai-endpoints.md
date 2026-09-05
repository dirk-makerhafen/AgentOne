---
name: OVHcloud AI Endpoints
url: "https://www.ovhcloud.com/en/public-cloud/ai-endpoints/"
setup_instructions: |
  1. Anonymous (no signup): POST to https://oai.endpoints.kepler.ai.cloud.ovh.net/v1 with no Authorization header (2 RPM per IP per model).
  2. For an API key: create an OVHcloud account with a Public Cloud project that has a payment method (Discovery-mode projects without one cannot use the service).
  3. In the project, go to AI & Machine Learning > AI Endpoints, generate an API key, store it securely, and pick a model from https://www.ovhcloud.com/en-gb/public-cloud/ai-endpoints/catalog/.
api_key_url: "https://www.ovhcloud.com/en-gb/public-cloud/ai-endpoints/catalog/"
default_api_key: public
limits:
  requests:
    minute: 2
---

OVHcloud AI Endpoints is a serverless EU-hosted API for open-weight models with a permanent keyless anonymous tier and OpenAI-compatible LLM routes.

**Free Tier:**

- Permanent anonymous tier: no signup, no key, no payment — throttled per IP.
- Authenticated use is pay-as-you-go per token (400 RPM per project per model); new accounts get a 1-month trial credit (amount unverified officially).
- Always-free models (non-LLM): Stable Diffusion XL, NVIDIA Riva TTS, Qwen3Guard moderation.

**Free Models:**

- Any catalog LLM is callable anonymously within the 2 RPM limit (representative snapshot, verify live in catalog): `Meta-Llama-3_3-70B-Instruct`, `Mistral-Nemo-Instruct-2407`, `Qwen2.5-VL-72B-Instruct` (vision), [`gpt-oss-120b`](../models/gpt-oss-120b.md), `gpt-oss-20b`, `Qwen3-32B`, `Qwen3-Coder-30B-A3B-Instruct` (code), `Mistral-Small-3.2-24B-Instruct-2506`, `Mistral-7B-Instruct-v0.3`, `Qwen3.5-397B-A17B` (roster rotates; verify live).

**Limits:**

- Anonymous: 2 requests per minute, per IP and per model (official; 429 on exceed).
- Authenticated with API key: 400 requests per minute, per Public Cloud project and per model (official).
- Payload caps: 2 MB default, 10 MB for vision-language models (official).
- No other usage limits (official capabilities page); playground LLM output capped at 1024 tokens (testing only).

**Notes:**

- Anonymous access: no account, key, card, or phone. Keyed access: account + project + payment method required.
- Phone verification: not documented (unknown for keyed signup).
- Data policy (official): user data not stored; EU-hosted, GDPR.
- Free path is IP-throttled and shared — suitable for prototyping, not production.
- Authenticated per-token prices are low (secondary compilation, verify billing doc), e.g. Llama-3.3-70B ~EUR 0.67/M, GPT-OSS-20B ~EUR 0.04 in / 0.15 out.

**Sources**

- https://docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/ai-endpoints-getting-started
- https://docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/ai-endpoints-capabilities
- https://www.ovhcloud.com/en/public-cloud/ai-endpoints/
- https://www.ovhcloud.com/en/public-cloud/ai-endpoints/catalog/
