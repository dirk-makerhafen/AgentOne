---
name: Cloudflare Workers AI
url: "https://www.cloudflare.com"
setup_instructions: |
  1. Sign up for a Cloudflare account at https://dash.cloudflare.com/sign-up/workers-and-pages.
  2. In the dashboard open the Workers AI page and select "Use REST API".
  3. Create a Workers AI API token (needs Workers AI Read and Edit permissions) and copy it together with your Account ID.
  4. POST to https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model} with header "Authorization: Bearer {token}".
api_key_url: "https://dash.cloudflare.com/?to=/:account/ai/workers-ai"
limits:
  requests:
    minute: 300
---

Workers AI includes a permanent daily free allocation of 10,000 Neurons (GPU-compute units) on both Workers Free and Workers Paid plans, shared across all models.

**Free Tier:**

- Permanent: 10,000 Neurons/day free (resets 00:00 UTC); overage is billed at $0.011/1,000 Neurons on Workers Paid and hard-fails on Workers Free.
- No paid plan needed to use the free allocation.

**Free Models:**

- No separate free-model list; all non-restricted catalog models draw from the same 10,000-Neuron pool at per-model neuron rates (representative, verify live in the models catalog).
- `@cf/meta/llama-3.1-8b-instruct` — text (official REST quickstart example).
- `@cf/meta/llama-3.3-70b-instruct-fp8-fast` — text, 26,668 in / 204,805 out neurons per M tokens.
- [`@cf/openai/gpt-oss-120b`](../models/gpt-oss-120b.md) — text, 31,818 in / 68,182 out neurons per M tokens.
- `@cf/mistralai/mistral-small-3.1-24b-instruct` — text, 31,876 in / 50,488 out neurons per M tokens.
- Paid billing required (Workers Paid or prepaid AI Gateway credits), current frontier table 2026-08-07: `@cf/moonshotai/kimi-k2.6`, `@cf/moonshotai/kimi-k2.7-code`, `@cf/zai-org/glm-5.2`. Previously listed `glm-5.3`, `glm-5.3-flash`, `@cf/deepseek-ai/deepseek-v4-flash-0731`, `deepseek-v4-pro-0813` are absent from the current limits page — **unverified** whether still gated, renamed, or removed; check the live models catalog.

**Limits:**

- Free quota: 10,000 Neurons/day (not tokens — omitted from frontmatter `tokens` for that reason).
- Request-rate caps by task (frontmatter `minute: 300` is Text Generation): Text Generation 300 req/min; ASR / Image-to-Text / Translation 720/min; Text Embeddings 3,000/min; Summarization 1,500/min.
- Frontier models per account per model: kimi-k2.6 / kimi-k2.7-code / glm-5.2 at 20 req/min standard, 50 req/min with prepaid AI Gateway credits on Unified billing.

**Notes:**

- Cloudflare account required; API token + Account ID required; card requirement for the free tier: **unknown**; phone verification: **unknown**.
- Native REST endpoint `https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}`; usage visible in the Workers AI dashboard.
- Local Wrangler inference counts toward limits; beta models may have lower limits.

**Sources**

- https://developers.cloudflare.com/workers-ai/platform/pricing/ (updated 2026-08-28)
- https://developers.cloudflare.com/workers-ai/platform/limits/
- https://developers.cloudflare.com/workers-ai/get-started/rest-api/
- Secondary (example IDs only): docs/free-tier-research/raw/awesome-free-llm-apis/Cloudflare Workers AI.json
