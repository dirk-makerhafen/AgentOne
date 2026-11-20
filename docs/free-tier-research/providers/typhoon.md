---
name: Typhoon API
url: "https://opentyphoon.ai"
api_base: "https://api.opentyphoon.ai/v1"
setup_instructions: |
  1. Create an account at https://opentyphoon.ai and get a free key from https://playground.opentyphoon.ai/api-key.
  2. Point an OpenAI-compatible client at https://api.opentyphoon.ai/v1.
  3. Use `typhoon-v2.5-30b-a3b-instruct` (Thai-optimized, 128K context) or `typhoon-v2.1-12b-instruct`.
api_key_url: "https://playground.opentyphoon.ai/api-key"
---

Typhoon API is SCB 10X's free research showcase. Account + key required, no payment. Verified 2026-11-20.

**Free Tier:**

- The official FAQ states the API is "a research showcase and free to use". No global token quota is published; only per-model request rates.
- Beta, provided as-is, no formal support. Higher limits are available by contacting contact@opentyphoon.ai.
- Production use is recommended via the paid Together.ai "API Pro" route; that is a separate product.

**Free Models:**

- `typhoon-v2.5-30b-a3b-instruct` — 128K context, tool use, Thai-optimized; 5 requests/sec, 200 requests/min. No vision.
- `typhoon-v2.1-12b-instruct` — 5 requests/sec, 200 requests/min (not in the catalog lead; added from official rate-limit docs).
- `typhoon-ocr` — 2 req/s, 20 req/min; `typhoon-asr-realtime` — 100 req/min. Both are non-chat.

**Limits:**

- No provider-wide numeric limits in frontmatter; the published caps are per-model and documented above.

**Notes:**

- Usage data is collected to improve the model/API ("never shared with third parties"). Do not send sensitive content.
- Outputs: SCB 10X claims no rights.
- Exact max output tokens and detailed tool-call wire shape are not published.

**Sources**

- https://docs.opentyphoon.ai/en/faq
- https://docs.opentyphoon.ai/en/rate-limits
- https://docs.opentyphoon.ai/en/api-reference
- https://docs.opentyphoon.ai/en/
- https://opentyphoon.ai
- docs/free-tier-research/raw/freellmapi-catalog/platforms/typhoon.json (discovery lead, verified 2026-11-20)
