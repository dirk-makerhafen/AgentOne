---
name: Groq
url: "https://console.groq.com"
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

**Free Models:**

- `openai/gpt-oss-120b` — 131K context, reasoning; flagship open-weight model.
- `openai/gpt-oss-20b` — 131K context.
- `openai/gpt-oss-safeguard-20b` — 131K context moderation variant.
- `qwen/qwen3.6-27b`, `qwen/qwen3.8-27b` — 131K context.
- `groq/compound`, `groq/compound-mini` — 131K context agentic systems with built-in tools.
- `meta-llama/llama-prompt-guard-2-22m`, `meta-llama/llama-prompt-guard-2-86m` — guard models.
- `whisper-large-v3`, `whisper-large-v3-turbo` — speech-to-text (audio-seconds metering).

**Limits:**

- Official Free Plan figures (console.groq.com/docs/rate-limits, fetched Sept 2026): gpt-oss-120b/-20b/-safeguard and qwen3.6/3.8-27b — 30 RPM / 1,000 RPD / 8K TPM / 200K TPD; compound/mini — 30 RPM / 250 RPD / 70K TPM; prompt-guard models — 30 RPM / 14.4K RPD / 15K TPM / 500K TPD; whisper — 20 RPM / 2,000 RPD / 7.2K audio-sec/hr / 28.8K audio-sec/day.
- Frontmatter values above are the `openai/gpt-oss-120b` Free figures as the representative LLM baseline; other models differ per table.
- Exceeding any dimension returns HTTP 429; usage headers (`x-ratelimit-*`, `retry-after`) report remaining quota.

**Notes:**

- Account required; API key required; no credit card and no phone verification reported (secondary source — not explicitly stated on official docs pages).
- Exact limits also visible per-organization at console.groq.com/settings/limits.

**Sources**

- https://console.groq.com/docs/rate-limits
- https://console.groq.com/docs/models
- https://console.groq.com/docs/quickstart
- https://groq.com/pricing
- Secondary: https://freellms.org/providers/groq (2026-08-06)
