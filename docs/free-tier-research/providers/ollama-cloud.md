---
name: Ollama Cloud
url: "https://ollama.com/"
setup_instructions: |
  1. Create an account at https://ollama.com/ (one account per person; `ollama signin` for CLI use).
  2. Create an API key at https://ollama.com/settings/keys and export it as OLLAMA_API_KEY.
  3. Call the native API at host https://ollama.com (e.g. POST https://ollama.com/api/chat, list via GET https://ollama.com/api/tags) with a Bearer key; the Free plan covers starter models from the monthly starter credits.
api_key_url: "https://ollama.com/settings/keys"
limits: {}
---

Ollama Cloud hosts open-weight models behind the same API surface as local Ollama, with a permanent $0 Free plan funded by monthly starter usage credits (transparent per-token pricing since 2026-09-01; old session/weekly caps removed).

**Free Tier:**

- Permanent Free plan ($0): a starter amount of monthly usage for a set of starter models only; adding extra credits unlocks all models with pay-as-you-go pricing, no subscription or service fees.
- Included usage resets monthly from signup date; no rollover. Included plan credits are consumed first, then the extra usage balance.
- Local inference on own hardware is always free and unlimited.
- Paid tiers: Pro $20/mo ($200/yr) with $60 credits/mo; Max $100/mo with $300 credits/mo; Team $500/mo with $1,000 shared credits/mo.

**Free Models:**

- Starter-model subset only; Ollama does not officially label which catalog models are "starter" — verify live at https://ollama.com/search?c=cloud. Representative catalog IDs (all pay full per-token rates once starter credits are exhausted or for non-starter models):
- [`deepseek-v4-flash`](../models/deepseek-v4-flash.md) (`deepseek-v4-flash`, $0.22 in / $0.66 out per 1M), [`deepseek-v4-pro`](../models/deepseek-v4-pro.md) (`deepseek-v4-pro`, $0.66/$1.98), [`gpt-oss:120b`](../models/gpt-oss-120b.md) (`gpt-oss:120b`, $0.15/$0.60), `gpt-oss:20b` ($0.07/$0.30), [`minimax-m3`](../models/minimax-m3.md) (`minimax-m3`, $0.60/$2.40), [`nemotron-3-nano`](../models/nemotron-3-nano-30b-a3b.md) (`nemotron-3-nano`, $0.06/$0.24), `nemotron-3-super`, `nemotron-3-ultra`, `gemma4` (links [`gemma4:31b`](../models/gemma-4-31b-it.md)), `qwen3.5:397b`, `glm-5.3` / `glm-5.3-flash`, `kimi-k3` ($3.00/$15.00), `mistral-large-3`.
- Peak pricing (12:00–18:00 UTC Mon–Fri) doubles some rates (e.g. `deepseek-v4-flash` $0.44/$1.32).

**Limits:**

- Concurrency (official): Free 1, Pro 3, Max/Team 10 concurrent requests; excess queues, then rejects when the queue is full. (Kept in body: concurrency is not a requests/tokens-over-time limit, so it does not go in frontmatter.)
- No documented RPM/RPD/TPM figures. The old 5-hour session / 7-day weekly limits no longer apply (removed under the 2026-09-01 pricing).

**Notes:**

- Account required; API key required. Credit card for Free plan: unknown. Phone verification: unknown.
- One account per person.
- Native API endpoints verified (`https://ollama.com/api/chat`, `/api/tags`, `/api/generate`); the OpenAI-compatible `/v1` surface is documented for the local server, and a cloud `https://ollama.com/v1` base URL is not documented — treat third-party claims of `https://api.ollama.com/v1` as unverified.
- Retired 2026-07-15 (use alternatives): `glm-4.7` → `glm-5.2`, `glm-5` → `glm-5.2`, `deepseek-v3.1:671b`/`deepseek-v3.2` → `deepseek-v4-flash`, `gemma3:*` → `gemma4:31b`, `minimax-m2.1` → `minimax-m3`.
- Hosted primarily in the US (overflow EU/Singapore) via NVIDIA Cloud Providers.
- Data policy (official): prompt/response data never logged or trained on; zero-retention required of partners.

**Sources**

- https://ollama.com/pricing (Free plan, credit amounts, per-model rates, concurrency — verified 2026-09-05)
- https://ollama.com/blog/transparent-pricing (2026-09-01 pricing change, removal of session/weekly limits)
- https://docs.ollama.com/cloud (native API host/endpoints, key creation, retirements)
- https://docs.ollama.com/api/authentication (API served at `https://ollama.com/api`, Bearer auth)
- https://docs.ollama.com/api/openai-compatibility (OpenAI `/v1` surface documented for local server)
