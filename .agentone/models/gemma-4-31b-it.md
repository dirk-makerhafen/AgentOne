---
name: Gemma 4 31B IT
developer: Google
canonical_id: google/gemma-4-31b-it
leaderboard_id: gemma-4-31b-it
leaderboard_rank: 81
family: gemma
context_window: 262144
max_output_tokens: 32768
reasoning: true
tool_call: true
structured_output: true
temperature: true
modalities:
  input: [text, image]
  output: [text]
open_weights: true
knowledge_cutoff: "2025-01"
providers:
  - name: UnoRouter
    file: unorouter
    model_id: gemma-4-31b-it:free
    conditions: ":free lane; account + key, no card"
    limits:
      requests:
        minute: 1
    verified: "2026-09-05"
  - name: Requesty
    file: requesty
    model_id: google/gemma-4-31b-it
    conditions: "Free-models tier ('free for now'); account + key, no card; quota shared across all free models combined"
    limits:
      requests:
        minute: 20
        day: 200
    verified: "2026-09-05"
  - name: InferX
    file: inferx
    model_id: gemma-4-31B-it-fp8
    conditions: "InferX Free $0/mo promo ('Free · 100% off'); account + key; promos rotate, re-verify pricing page"
    verified: "2026-09-05"
  - name: LLM7.io
    file: llm7
    model_id: gemma4:31b
    conditions: "Live-verified free `turbo` ID; anonymous with `api_key=\"unused\"` or free token; `turbo` roster rotates"
    verified: "2026-09-05"
  - name: SambaNova Cloud
    file: sambanova
    model_id: gemma-4-31B-it
    conditions: "Free tier (preview); account + key, no card; preview models may be removed at short notice"
    limits:
      requests:
        minute: 20
        day: 20
      tokens:
        day: 200000
    verified: "2026-09-05"
  - name: OpenRouter
    file: openrouter
    model_id: google/gemma-4-31b-it:free
    conditions: "Permanent `:free` variant; account + key, no card; free-model caps apply account-wide; roster rotates"
    verified: "2026-09-05"
  - name: AIHubMix
    file: aihubmix
    model_id: gemma-4-31b-it-free
    conditions: "Free-model lane; account + key, no card; trial-use, 429s possible under load"
    verified: "2026-09-05"
---

Gemma 4 31B IT is Google DeepMind's 30.7B dense multimodal instruction model (released 2026-04-02): text + image in / text out, 256K official context (262144 served on API routes), configurable thinking mode, native function calling, 140+ languages, Apache 2.0.

**Capabilities:**

- Reasoning (configurable thinking mode), tool/function calling, structured output, temperature control (official model card / NVIDIA NIM listing).
- Text + image in / text out (video consumable as frame sequences per NVIDIA listing); 256K official context, 262144 on API routes.
- Open weights under Apache 2.0 (ready for commercial/non-commercial use).

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [UnoRouter](../providers/unorouter.md) | `gemma-4-31b-it:free` | `:free` lane; account + key, no card | ~1 req/min per user + upstream caps | 2026-09-05 |
| [Requesty](../providers/requesty.md) | `google/gemma-4-31b-it` | Free-models tier ("free for now"); account + key, no card | New orgs: 200 req/day + 20 req/min shared across all free models combined | 2026-09-05 |
| [InferX](../providers/inferx.md) | `gemma-4-31B-it-fp8` | InferX Free $0/mo promo ("Free · 100% off"); account + key | No published numbers | 2026-09-05 |
| [LLM7.io](../providers/llm7.md) | `gemma4:31b` | Live-verified free `turbo` ID; anonymous with `api_key="unused"` or free token | None published combo-specific; provider-wide Anonymous/Free-token quotas apply (see provider file); `turbo` roster rotates | 2026-09-05 |
| [SambaNova Cloud](../providers/sambanova.md) | `gemma-4-31B-it` | Free tier (preview); account + key, no card | Provider-wide free tier: 20 RPM / 20 RPD / 200K TPD; preview models may be removed at short notice | 2026-09-05 |
| [OpenRouter](../providers/openrouter.md) | `google/gemma-4-31b-it:free` | Permanent `:free` variant; account + key, no card | None published combo-specific; provider-wide free-model caps apply (see provider file); roster rotates | 2026-09-05 |
| [AIHubMix](../providers/aihubmix.md) | `gemma-4-31b-it-free` | Free-model lane; account + key, no card | None published; free versions are trial-use (limited resources, 429s possible under load) | 2026-09-05 |

**Notes:**

- Fixture-observed (re-verification lead, not in table): a `gemma-4-31b-it:free` row on Kenari and a $0 row on Nvidia NIM — confirm live via `GET /v1/models` / build.nvidia.com before use.
- NOT the same model (do not conflate; gap for a future card): FastRouter's `google/gemma4-26b:free` and OpenRouter's `google/gemma-4-26b-a4b-it:free` are the 26B MoE variant (26B total / 4B active), a different checkpoint from this 31B dense card.
- Skipped leads: Ollama Cloud catalogs `gemma4:31b` at paid per-token rates under monthly starter credits — not a standing free row. Pollinations lists bare `gemma-4-31b` with equivalence to this card explicitly unverified in its provider file — not claimed. FastRouter documents no `gemma-4-31b-it` free row. SiliconFlow lists `google/gemma-4-31B-it` but fixtures report nonzero prices — treated as paid per its provider file.

**Sources**

- https://huggingface.co/google/gemma-4-31B-it (official model card: 30.7B dense, thinking mode, Jan 2025 cutoff, Apache 2.0)
- https://build.nvidia.com/google/gemma-4-31b-it (official listing: text+image in, 256K context, commercial-use ready)
- https://docs.api.nvidia.com/nim/reference/google-gemma-4-31b-it (training cutoff Jan 2025, 140+ languages)
- https://openrouter.ai/google/gemma-4-31b-it%3Afree (262K context, free variant)
- https://api.llm7.io/v1/models (live catalog: `gemma4:31b` as `turbo`/free ID)
- https://docs.sambanova.ai/docs/en/models/rate-limits (free-tier row incl. `gemma-4-31B-it` preview)
- https://aihubmix.com/models/free (`gemma-4-31b-it-free` $0/M row)
- raw/opencode-models-api/google/model_gemma-4-31b-it.json (capabilities/context — discovery data)
- https://unorouter.com/en/models
- https://docs.requesty.ai/features/free-models
- https://inferx.net/pricing/endpoints
