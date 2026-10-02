---
name: Groq
url: "https://console.groq.com"
api_base: "https://api.groq.com/openai/v1"
litellm_prefix: groq
setup_instructions: |
  1. Sign up at https://console.groq.com (email or Google/GitHub login).
  2. Open API Keys in the sidebar and create an API key.
  3. Export it (`export GROQ_API_KEY=<key>`) and call `https://api.groq.com/openai/v1`.
api_key_url: "https://console.groq.com/keys"
limits:
  requests:
    minute: 30
    day: 1000
  tokens:
    minute: 8000
    day: 200000
---

GroqCloud is Groq's LPU-powered inference API with a permanent rate-limited free plan and OpenAI-compatible endpoints.

**Free Tier:**

- Permanent free plan, pay-as-you-go Developer plan and Enterprise above it; limits apply per organization.
- Cached tokens do not count toward rate limits.
- Re-verified 2026-09-05 against the official rate-limits page: Free Plan table lists 12 model rows (see model-specific limits below).

**Free Models:**

- [`openai/gpt-oss-120b`](../models/gpt-oss-120b.md) — 131,072 context, 65,536 max completion; reasoning; flagship open-weight model.
- `openai/gpt-oss-20b` — 131,072 context, 65,536 max completion; reasoning.
- `openai/gpt-oss-safeguard-20b` — 131,072 context moderation variant; reasoning.
- [`qwen/qwen3.6-27b`](../models/qwen3.6-27b.md), [`qwen/qwen3.8-27b`](../models/qwen3.8.md) — ~131K context (qwen3.8 listed at 131,042), multimodal input, thinking/instruct dual mode, `reasoning_effort` support on qwen3.6.
- `groq/compound`, `groq/compound-mini` — 131,072 context agentic systems with built-in tools (8,192 max completion).
- `meta-llama/llama-prompt-guard-2-22m`, `meta-llama/llama-prompt-guard-2-86m` — guard models, 512 context.
- `whisper-large-v3`, `whisper-large-v3-turbo` — speech-to-text (audio-seconds metering).
- `canopylabs/orpheus-arabic-saudi`, `canopylabs/orpheus-v1-english` — TTS, 4,000 context.

**Limits:**

- Official Free Plan figures (console.groq.com/docs/rate-limits, re-verified 2026-09-05): gpt-oss-120b/-20b/-safeguard and qwen3.6/3.8-27b — 30 RPM / 1,000 RPD / 8K TPM / 200K TPD; compound/mini — 30 RPM / 250 RPD / 70K TPM (no TPD listed); prompt-guard models — 30 RPM / 14.4K RPD / 15K TPM / 500K TPD; whisper — 20 RPM / 2,000 RPD / 7.2K audio-sec/hr / 28.8K audio-sec/day; orpheus models — 10 RPM / 100 RPD / 1.2K TPM / 3.6K TPD.
- Frontmatter values above are the `openai/gpt-oss-120b` Free figures as the representative LLM baseline; other models differ per table.
- Exceeding any dimension returns HTTP 429; usage headers (`x-ratelimit-*`, `retry-after`) report remaining quota.

**Notes:**

- Account required; API key required. Upgrading Free to Developer requires a payment method (card, US bank, or SEPA), so the Free tier itself requires no card. Phone verification: unverified in official docs.
- Exact limits also visible per-organization at console.groq.com/settings/limits.
- `llama-3.1-8b-instant` / `llama-3.3-70b-versatile` now appear as Enterprise rows on the models page and are absent from the current Free Plan rate-limits table — not listed as free.
- Endpoint: `https://api.groq.com/openai/v1` (OpenAI-compatible; live model list at `/openai/v1/models`).

**Sources**

- https://console.groq.com/docs/rate-limits
- https://console.groq.com/docs/models
- https://console.groq.com/docs/quickstart
- https://console.groq.com/docs/billing-faqs
- https://groq.com/pricing
