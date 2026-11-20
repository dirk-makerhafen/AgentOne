---
name: AI Horde
url: "https://aihorde.net"
api_base: "https://oai.aihorde.net/v1"
default_api_key: "0000000000"
setup_instructions: |
  1. Point an OpenAI-compatible client at https://oai.aihorde.net/v1.
  2. Use the anonymous sentinel key `0000000000`, or omit auth (the front end falls back to it).
  3. Optionally register a free account at https://aihorde.net/register for a personal key and higher queue priority.
  4. Discover currently served models with GET https://oai.aihorde.net/v1/models.
api_key_url: "https://aihorde.net/register"
---

AI Horde is a volunteer-distributed inference network with a genuinely free anonymous lane. No account, key, or payment method is required; the anonymous sentinel key `0000000000` works out of the box. Verified 2026-11-20.

**Free Tier:**

- Keyless anonymous access; no card, no account. A free registered account only raises queue priority (registered users start at 25 kudos, anonymous at 0).
- No fixed RPM/RPD/TPM/TPD. Work is metered through a kudos queue: the free output allowance is roughly 512–4096 tokens depending on eligible-worker load; larger requests require held kudos and otherwise fail `403 KudosUpfront`.
- Per-request bounds: `max_tokens` 16–16384 (default 512), up to 1024 messages, 36 MiB body, 300 s non-stream / 600 s stream wait.

**Free Models:**

- There is no stable free-model list. The authoritative roster is live `GET https://oai.aihorde.net/v1/models`; on 2026-11-20 it returned 21 models, while 4 sampled catalog rows were no longer served.
- Catalog-reported IDs in `raw/freellmapi-catalog/platforms/aihorde.json` are leads only. Do not build per-model cards from them: worker/quantization changes hourly and served context is usually 4–8K regardless of the model's native window.

**Limits:**

- No numeric request or token limits are published; kudos-derived amounts are intentionally omitted from frontmatter `limits`.

**Notes:**

- Volunteer queue latency ranges from seconds to minutes; quality varies by worker and quantization.
- Official docs forward `tools`, `tool_choice`, `parallel_tool_calls`, `reasoning_content`, the `x_horde` extension object, and SSE streaming. The catalog's "no tool calling / no streaming" quirk is stale and contradicted by official docs.
- Request normalization: `max_tokens < 16` is rejected; `stop` handling and worker-side `max_tokens` clamping apply.

**Sources**

- https://aihorde.net/
- https://aihorde.net/register
- https://haidra-org.github.io/AI-Horde/how-to/send_chat_completions
- https://haidra-org.github.io/AI-Horde/haidra-assets/docs/kudos
- https://oai.aihorde.net/v1/models
- docs/free-tier-research/raw/freellmapi-catalog/platforms/aihorde.json (discovery lead, verified 2026-11-20)
