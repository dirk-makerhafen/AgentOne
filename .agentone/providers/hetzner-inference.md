---
name: Hetzner Inference API
url: "https://experiments.hetzner.com"
api_base: "https://inference.hetzner.com/api/v1"
setup_instructions: |
  1. Sign in with your Hetzner customer account at https://experiments.hetzner.com.
  2. In the left navigation under APPS, select "Inference".
  3. Click "Create API Token" (top-right) and copy the token.
  4. Point any OpenAI-compatible client at base URL https://inference.hetzner.com/api/v1 using the token as the API key.
  5. Resolve the current roster live via GET /v1/models (the response is definitive; selection changes during the experiment).
api_key_url: "https://experiments.hetzner.com/inference"
limits:
  requests:
    minute: 10
  tokens:
    input:
      minute: 4000000
    output:
      minute: 100000
---

OpenAI-compatible inference API for open-weight LLMs, hosted by Hetzner on its own hardware under its Experiments platform.

**Free Tier:**

- Free of charge for as long as the API remains in experimental status; Hetzner states users will be notified by email in advance of any status change.

**Free Models:**

- [`Qwen/Qwen3.6-35B-A3B-FP8`](../models/qwen3.6-35b-a3b.md) — 262,144 tokens context, text + image (vision), MoE 35B total / 3B active, Apache 2.0.
- [`Qwen3.8-27B`](../models/qwen3.8.md) — 262,144 tokens context, text + image, dense, Apache 2.0. Representative: verify live via `GET /v1/models` (roster changes during the experiment).

**Limits:**

- 10 requests per 60 seconds per API key; 4M input tokens and 100k output tokens per 60 seconds per API key (60s windows recorded as per-minute in frontmatter); HTTP 429 on exceed.

**Notes:**

- Account required: yes (Hetzner customer account — Experiments is open to all Hetzner customers). API key required: yes (Experiments token). Payment/billing info required: no (no billing exists yet; "no guarantees, but no cost either"). Phone verification: unknown.
- No SLA, no backups, no data processing agreement — unsuitable for production or personal data. Hetzner logs request timestamps and token counts; request/response content is not stored.
- Endpoints: `/v1/models`, `/v1/completions`, `/v1/chat/completions` on base URL `https://inference.hetzner.com/api/v1` (docs-confirmed).

**Sources**

- https://docs.hetzner.com/general/company-and-policy/experiments/inference/ (models, limits, free terms, endpoints, verified 2026-09-05)
- https://docs.hetzner.com/general/company-and-policy/experiments/experiments-platform/ (customer-account access, no-cost terms, verified 2026-09-05)
- https://www.hetzner.com/blog/inference-experiment/ (experiment context)
- https://community.hetzner.com/tutorials/opencode-with-hetzner-inference-api-systemd-sandbox/ (setup flow)
