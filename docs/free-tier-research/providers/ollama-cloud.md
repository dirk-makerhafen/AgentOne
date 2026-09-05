---
name: Ollama Cloud
url: "https://ollama.com/"
setup_instructions: |
  1. Sign in at https://ollama.com/ and download the Ollama client.
  2. Create an API key at https://ollama.com/settings/keys.
  3. Point an OpenAI-compatible client at https://ollama.com/v1 (or use the native API at https://ollama.com/api) with the key.
api_key_url: "https://ollama.com/settings/keys"
limits: {}
---

Ollama Cloud hosts open-weight models behind the same API surface as local Ollama, with a permanent $0 Free plan funded by starter usage credits.

**Free Tier:**

- Permanent Free plan ($0): starter usage credits included, access to starter models only, 1 concurrent request.
- Adding extra credits unlocks all models; local inference on own hardware is always free and unlimited.
- Included usage resets monthly from signup date; no rollover.

**Free Models:**

- Starter-model subset only; Ollama does not officially label which catalog models are "starter" (representative, verify live at https://ollama.com/search?c=cloud).
- Catalog includes (representative, verify live): `deepseek-v4-flash`, `deepseek-v4-pro`, `gpt-oss:20b`, `gpt-oss:120b`, `qwen3.5:397b`, `kimi-k3`, `minimax-m3`, `nemotron-3-ultra`, `mistral-large-3`, `glm-5.3`, `glm-5.3-flash` — full catalog requires added credits.

**Limits:**

- Concurrency (official): Free 1, Pro 3, Max/Team 10; excess requests queue, then reject when queue is full.
- Usage metered in tokens at per-model rates (e.g. `gpt-oss:20b` $0.07 in / $0.30 out per 1M; `deepseek-v4-flash` $0.22/$0.66; peak pricing 12:00–18:00 UTC Mon–Fri doubles some rates).
- No documented RPM/RPD/TPM figures; older secondary sources cite 5-hour session / 7-day weekly limits, but the live pricing page describes monthly credits — discrepancy flagged, treat monthly-credit wording as current.
- Paid tiers: Pro $20/mo ($200/yr) with $60 credits/mo (~50x Free); Max $100/mo with $300 credits/mo.

**Notes:**

- Account required; API key required.
- Credit card for Free plan: unknown. Phone verification: unknown.
- One account per person.
- Hosted primarily in the US (overflow EU/Singapore) via NVIDIA Cloud Providers.
- Data policy (official): prompt/response data never logged or trained on; zero-retention required of partners.

**Sources**

- https://ollama.com/pricing
- https://docs.ollama.com/cloud
- https://ollamatps.com/limits (secondary, verified vs pricing 2026-08-15)
- https://devtoolhub.com/ollama-cloud-free-vs-pro-limits-pricing-2026/ (secondary, 2026-08-28)
