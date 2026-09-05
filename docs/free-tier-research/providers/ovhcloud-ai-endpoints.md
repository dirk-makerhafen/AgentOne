---
name: OVHcloud AI Endpoints
url: "https://www.ovhcloud.com/en/public-cloud/ai-endpoints/"
setup_instructions: |
  1. Anonymous (no signup): POST to https://oai.endpoints.kepler.ai.cloud.ovh.net/v1 with no Authorization header (2 RPM per IP per model; verified against official docs 2026-09-05).
  2. For an API key: create an OVHcloud account with a Public Cloud project that has a payment method (Discovery-mode projects without one cannot use the service — official getting-started guide).
  3. In the project, go to AI & Machine Learning > AI Endpoints, click "Generate my first access Key" / "+ Create a new API key" (name + optional description/expiry), store the key securely, and pick a model from https://www.ovhcloud.com/en-gb/public-cloud/ai-endpoints/catalog/.
api_key_url: "https://www.ovhcloud.com/en-gb/public-cloud/ai-endpoints/catalog/"
default_api_key: public
limits:
  requests:
    minute: 2
---

OVHcloud AI Endpoints is a serverless EU-hosted API for open-weight models with a permanent keyless anonymous tier and OpenAI-compatible LLM routes.

**Free Tier:**

- Permanent anonymous tier: no signup, no key, no payment — throttled per IP (official capabilities page, verified 2026-09-05).
- Authenticated use is billed per token (400 RPM per project per model); it requires a payment method on the project, so it is not a free tier. A "1-month trial credit" for new accounts is rumored in secondary sources — amount and availability unverified officially.
- Always-free non-LLM models (secondary-reported, verify live in the catalog): Stable Diffusion XL, NVIDIA Riva TTS, Qwen3Guard moderation.

**Free Models:**

- Any catalog LLM is callable anonymously within the 2 RPM limit (representative snapshot, verify live in catalog): `Meta-Llama-3_3-70B-Instruct`, `Mistral-Nemo-Instruct-2407`, `Qwen2.5-VL-72B-Instruct` (vision), [`gpt-oss-120b`](../models/gpt-oss-120b.md) (matches the model card's OVHcloud row ID, verified 2026-09-05), [`gpt-oss-20b`](../models/gpt-oss-20b.md), [`Qwen3-32B`](../models/qwen3-32b.md), `Qwen3-Coder-30B-A3B-Instruct` (code), `Mistral-Small-3.2-24B-Instruct-2506`, `Mistral-7B-Instruct-v0.3`, [`Qwen3.5-397B-A17B`](../models/qwen3.5-397b.md) (roster rotates; verify live).
- The official getting-started guide uses `gpt-oss-120b` and `gpt-oss-20b` as its worked examples (reasoning/code models).

**Limits:**

- Anonymous: 2 requests per minute, per IP and per model (official; 429 on exceed — verified 2026-09-05).
- Authenticated with API key: 400 requests per minute, per Public Cloud project and per model (official — keyed tier requires a payment method, not free).
- Payload caps: 2 MB default, 10 MB for vision-language models (official — verified 2026-09-05).
- No other usage limits (official capabilities page: "does not impose any usage limits for API requests, apart from the rate and payload size limiting"); playground LLM output capped at 1024 tokens (testing only).

**Notes:**

- Anonymous access: no account, key, card, or phone. Keyed access: account + project + payment method required.
- Phone verification: not documented (unknown for keyed signup).
- Data policy (official): user data not stored; EU-hosted (Gravelines, France), GDPR.
- Free path is IP-throttled and shared — suitable for prototyping, not production.
- Authenticated per-token prices are low (secondary compilation, verify billing doc), e.g. Llama-3.3-70B ~EUR 0.67/M, GPT-OSS-20B ~EUR 0.04 in / 0.15 out.

**Sources**

- https://docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/ai-endpoints-getting-started (key steps, Discovery-mode exclusion, 2/400 RPM, 1024-token playground cap — verified 2026-09-05)
- https://docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/ai-endpoints-capabilities (rate/payload limits, no usage limits, GDPR — verified 2026-09-05)
- https://docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/ai-endpoints-responses-api (endpoint `https://oai.endpoints.kepler.ai.cloud.ovh.net/v1` in code samples — verified 2026-09-05)
- https://www.ovhcloud.com/en/public-cloud/ai-endpoints/
- https://www.ovhcloud.com/en/public-cloud/ai-endpoints/catalog/
