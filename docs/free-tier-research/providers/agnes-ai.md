---
name: Agnes AI
url: "https://agnes-ai.com"
setup_instructions: |
  1. Sign up or log in at the Agnes AI international platform (https://platform.agnes-ai.com).
  2. Open the API Key section in the developer console and create a key; copy and store it immediately (the complete key is normally shown only once).
  3. Set the request base URL to https://apihub.agnes-ai.com/v1 and send OpenAI-compatible requests with header `Authorization: Bearer YOUR_API_KEY`, using an exact model ID such as `agnes-2.5-flash`.
api_key_url: "https://platform.agnes-ai.com"
limits:
  requests:
    minute: 20
---

Unified OpenAI-compatible API for Agnes text, image, video, and multimodal models; core flash models are free indefinitely (verified 2026-09-05).

**Free Tier:**

- Core AI models free to use indefinitely per platform FAQ — no time limit stated (verified 2026-09-05). Free/default users are limited to basic RPM access; higher RPM and subscription quotas require a paid Token Plan or enterprise verification.

**Free Models:**

- [`agnes-2.5-flash`](../models/agnes-2.5-flash.md) — text, input and output currently $0/M (list $0.03/$0.15). (Deprecated `agnes-2.0-flash` is deliberately not catalogued — superseded ≥1yr-old generation, see README "Filenames" rule.)
- `agnes-image-2.0-flash`, `agnes-image-2.1-flash`, `agnes-image-2.5-flash` — image generation, all output-resolution tiers and input reference images currently $0.
- `agnes-video-v2.0` — video generation, currently $0/s.
- `agnes-video-2.5-flash` — video generation, currently $0/s but explicitly a limited-time free promotion (not stated as indefinite).
- Paid (not free): `agnes-2.5-pro` (billed at published Pro-tier prices); plain `agnes-video-2.5` ($0.025–$0.055/s by resolution + $0.005/image from the 6th input image onward). Hosted `agnes-2.5-pro-alpha` API is deprecated; its prices are retained as historical records.

**Limits:**

- Text-model RPM for free/default users: Allowed 30, Effective 20 (frontmatter uses the effective figure). Enterprise verified: 60/40. Token Plan keys: 1000 RPM plus subscription quotas (paid plans only).
- **Model-specific limits (body only, verified 2026-09-05):** image free/default RPM by output tier — 1K: 20 effective; 2K: 10; 3K: 1; 4K: 1. Video free/default RPM: 1 effective. Multiple keys of the same type share one limit pool; creating more keys does not raise limits.

**Notes:**

- Account required: yes. API key required: yes. Payment/billing info required: unknown (no card requirement documented for free use). Phone verification: unknown.
- Account bill is the source of truth; promotional $0 prices and end dates are subject to platform announcement.
- Model card: [agnes-2.5-flash](../models/agnes-2.5-flash.md).

**Sources**

- https://wiki.agnes-ai.com/en/docs/pricing (free/$0 prices, deprecations verified 2026-09-05)
- https://wiki.agnes-ai.com/en/docs/faqs (indefinite free use, key steps verified 2026-09-05)
- https://wiki.agnes-ai.com/en/docs/tokenplan (RPM limits, Token Plan quotas verified 2026-09-05)
- https://wiki.agnes-ai.com/en/docs/quickstart (base URL, auth verified 2026-09-05)
- https://wiki.agnes-ai.com/en/docs/overview (OpenAI compatibility, base URL verified 2026-09-05)
- https://wiki.agnes-ai.com/en/docs/agnes-image-25-flash
