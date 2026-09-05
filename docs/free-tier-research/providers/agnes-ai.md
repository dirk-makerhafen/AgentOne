---
name: Agnes AI
url: "https://agnes-ai.com"
setup_instructions: |
  1. Sign up for an Agnes AI Platform account.
  2. Log in to the developer dashboard and open the API Key management page.
  3. Create and copy your API key.
  4. Set the request base URL to https://apihub.agnes-ai.com/v1 and call using the OpenAI-compatible format with your key.
api_key_url: "https://agnes-ai.com/en/docs/quickstart"
limits:
  requests:
    minute: 20
---

Unified OpenAI-compatible API for Agnes text, image, video, and multimodal models; core flash models are free indefinitely.

**Free Tier:**

- Core flash models free to use indefinitely per platform FAQ; no time limit stated.

**Free Models:**

- `agnes-2.5-flash` — text, input and output currently $0/M (list $0.03/$0.15). (`agnes-2.0-flash` is deprecated per the pricing page — migrate to 2.5-flash.)
- `agnes-image-2.0-flash`, `agnes-image-2.1-flash`, `agnes-image-2.5-flash` — image generation, currently free.
- `agnes-video-v2.0`, `agnes-video-2.5-flash` — video generation, currently free. (Plain `agnes-video-2.5` is paid: $0.025–$0.055/s + $0.005/image from the 6th image onward.)
- Paid (not free): `agnes-2.5-pro` ($0.45/M input, $0.90/M output). (Hosted `agnes-2.5-pro-alpha` API is deprecated; its prices are retained as historical records.)

**Limits:**

- Text-model RPM for free/default users: Allowed 30, Effective 20 (frontmatter uses the effective figure). Enterprise verified: 60/40. Token Plan keys: 1000 RPM plus subscription quotas (paid plans only).

**Notes:**

- Account required: yes. API key required: yes. Payment/billing info required: unknown (no card requirement documented for free use). Phone verification: unknown.
- Direct dashboard/console URL for key creation is unknown beyond "developer dashboard" in docs; api_key_url points to the verified quickstart guide.
- Promotional $0 pricing end dates subject to platform announcement; account bill is source of truth.

**Sources**

- https://agnes-ai.com/en/docs/overview
- https://agnes-ai.com/en/docs/quickstart
- https://agnes-ai.com/en/docs/faqs
- https://agnes-ai.com/en/docs/tokenplan
- https://www.agnes-ai.com/en/docs/pricing
- https://wiki.agnes-ai.com/en/docs/pricing (deprecations verified 2026-09-05)
- https://wiki.agnes-ai.com/en/docs/agnes-image-25-flash
