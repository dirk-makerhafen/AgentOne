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
  input:
  - text
  - image
  output:
  - text
open_weights: true
knowledge_cutoff: 2025-01
---

Gemma 4 31B IT is Google DeepMind's 30.7B dense multimodal instruction model (released 2026-04-02): text + image in / text out, 256K official context (262144 served on API routes), configurable thinking mode, native function calling, 140+ languages, Apache 2.0.

**Capabilities:**

- Reasoning (configurable thinking mode), tool/function calling, structured output, temperature control (official model card / NVIDIA NIM listing).
- Text + image in / text out (video consumable as frame sequences per NVIDIA listing); 256K official context, 262144 on API routes.
- Open weights under Apache 2.0 (ready for commercial/non-commercial use).

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
