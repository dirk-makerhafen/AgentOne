---
name: MiniMax M3
developer: MiniMax
canonical_id: minimax/minimax-m3
leaderboard_id: minimax-m3
family: minimax
context_window: 1000000
max_output_tokens: 262144
reasoning: true
tool_call: true
temperature: true
modalities:
  input: [text, image, video]
  output: [text]
open_weights: true
providers:
  - name: AIHubMix
    file: aihubmix
    model_id: minimax-m3-free
    conditions: "Free-model lane; account + key, no card; trial-use, 429s possible under load"
    verified: "2026-09-05"
  - name: Kilo Code
    file: kilo-code
    model_id: minimax/minimax-m3:free
    conditions: "Standing `:free` lane; anonymous keyless access allowed (200 req/hour/IP); authenticated free-model limits unpublished"
    verified: "2026-09-05"
  - name: OpenRouter
    file: openrouter
    model_id: minimax/minimax-m3:free
    conditions: "Permanent `:free` variant; account + key, no card; free-model caps apply account-wide; roster rotates"
    verified: "2026-09-05"
---

MiniMax M3 is MiniMax's multimodal long-context flagship (released 2026-06-01): a ~428B-total / ~23B-active MoE with 1M context, native text+image+video input, and open weights under the MiniMax Community License (not MIT/Apache — verify before commercial use).

**Capabilities:**

- Reasoning (adaptive thinking), tool/function calling, temperature control (official API docs; fixture-consistent).
- Text + image + video in / text out; 1M context, up to 262144 max output (official model page).
- Open weights under the MiniMax Community License (weights on Hugging Face since 2026-06-02) — not MIT/Apache; commercial terms need verification.

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [AIHubMix](../providers/aihubmix.md) | `minimax-m3-free` | Free-model lane; account + key, no card | None published; free versions are trial-use (limited resources, 429s possible under load) | 2026-09-05 |
| [Kilo Code](../providers/kilo-code.md) | `minimax/minimax-m3:free` | Standing `:free` lane; anonymous keyless access allowed | 200 req/hour per IP anonymous; authenticated free-model limits unpublished | 2026-09-05 |
| [OpenRouter](../providers/openrouter.md) | `minimax/minimax-m3:free` | Permanent `:free` variant; account + key, no card | None published combo-specific; provider-wide free-model caps apply (see provider file); roster rotates | 2026-09-05 |

**Notes:**

- Fixture-observed (re-verification leads, not in table): $0 `minimax-m3` rows on Kenari, Nvidia NIM, and the opencode-models fixture set — confirm live before use. Pollinations lists bare `minimax` (not `minimax-m3`) with equivalence explicitly unverified — not claimed. Ollama Cloud catalogs `minimax-m3` at paid per-token rates under monthly starter credits — not a standing free row. StreamLake Vanchin maps base models to per-user endpoint IDs with login-gated eligibility — no 1:1 free ID assertable.
- MiniMax's own platform is paid ($0.30/$1.20 per 1M up to 512K prompt, double above) and has no provider file yet; do not confuse fixture $0 rows on paid gateways with standing free tiers.

**Sources**

- https://www.minimax.io/blog/minimax-m3 (official: 2026-06-01 release, 1M context, native multimodality)
- https://huggingface.co/MiniMaxAI/MiniMax-M3 (official weights, 428B/23B MoE, 262144 max output, Community License)
- https://platform.minimax.io/docs/release-notes/models (official API listing)
- https://aihubmix.com/pricing
- https://kilo.ai/docs/getting-started/using-kilo-for-free
- https://openrouter.ai/api/v1/models (live `:free` roster)
- raw/opencode-models-api/minimax/model_MiniMax-M3.json (capabilities/context — discovery data)
