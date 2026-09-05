---
name: Hetzner Inference API
url: "https://experiments.hetzner.com"
setup_instructions: |
  1. Sign in with your Hetzner customer account at https://experiments.hetzner.com.
  2. In the left navigation under APPS, select "Inference".
  3. Click "Create API Token" (top-right) and copy the token.
  4. Point any OpenAI-compatible client at base URL https://inference.hetzner.com/api/v1 using the token as the API key.
api_key_url: "https://experiments.hetzner.com"
limits:
  requests:
    minute: 10
---

OpenAI-compatible inference API for open-weight LLMs, hosted by Hetzner under its Experiments platform.

**Free Tier:**

- Free of charge for as long as the API remains in experimental status; Hetzner states users will be notified by email in advance of any status change.

**Free Models:**

- `Qwen/Qwen3.6-35B-A3B-FP8` — 262,144 tokens context, text + image (vision), MoE 35B total / 3B active.
- `Qwen3.8-27B` — 262,144 tokens context, text + image. Representative, verify live via `GET /v1/models` (roster changes during the experiment).

**Limits:**

- 10 requests per 60 seconds per API key; 4M input tokens and 100k output tokens per 60 seconds per API key; HTTP 429 on exceed. Token-window figures documented here but omitted from frontmatter (no per-input/output split in schema).

**Notes:**

- Account required: yes (Hetzner customer account). API key required: yes (Experiments token). Payment/billing info required: no (no billing exists yet). Phone verification: unknown.
- No SLA, no backups, no data processing agreement — unsuitable for production or personal data. Hetzner logs request timestamps and token counts; request/response content is not stored.

**Sources**

- https://docs.hetzner.com/general/company-and-policy/experiments/inference/
- https://docs.hetzner.com/general/company-and-policy/experiments/experiments-platform/
- https://www.hetzner.com/blog/inference-experiment/
- https://community.hetzner.com/tutorials/opencode-with-hetzner-inference-api-systemd-sandbox/
