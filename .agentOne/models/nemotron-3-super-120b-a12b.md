---
name: Nemotron 3 Super 120B A12B
developer: Nvidia
canonical_id: nvidia/nemotron-3-super-120b-a12b
leaderboard_id: nemotron-3-super-120b-a12b
leaderboard_rank: 151
family: nemotron
context_window: 262144
reasoning: true
tool_call: true
temperature: true
modalities:
  input: [text]
  output: [text]
open_weights: true
providers:
  - name: Kilo Code
    file: kilo-code
    model_id: nvidia/nemotron-3-super-120b-a12b:free
    conditions: "Standing `:free` lane; anonymous keyless access allowed, no account/key/card; roster rotates"
    verified: "2026-09-05"
  - name: OpenRouter
    file: openrouter
    model_id: nvidia/nemotron-3-super-120b-a12b:free
    conditions: "Permanent `:free` variant; account + key, no card; free-model caps apply account-wide; roster rotates"
    verified: "2026-09-05"
  - name: Kenari
    file: kenari
    model_id: nemotron-3-super-120b-a12b:free
    conditions: "`:free` lane billed Rp 0 (live-catalog-observed 2026-09-05); account + key (`kn-...`), no top-up; confirm via GET /v1/models"
    verified: "2026-09-05"
  - name: Requesty
    file: requesty
    model_id: nvidia/nemotron-3-super-120b-a12b
    conditions: "Free-models tier ('free for now'); account + key, no card; quota shared across all free models combined"
    limits:
      requests:
        minute: 20
        day: 200
    verified: "2026-09-05"
  - name: FastRouter
    file: fastrouter
    model_id: nvidia/nemotron-3-super:free
    conditions: "⚠ `:free` lane; org must hold a paid credit balance above $1 or free calls 402 (whether signup credits satisfy this is unverified)"
    limits:
      requests:
        day: 10
    verified: "2026-09-05"
---

Nemotron 3 Super 120B A12B is Nvidia's large hybrid MoE (120B total / 12B active) for agentic workflows, long-context reasoning, and high-volume workloads. It is the Super sibling of the Nemotron 3 family — not the Nano model ([Nemotron 3 Nano 30B A3B](nemotron-3-nano-30b-a3b.md)).

**Capabilities:**

- Reasoning trace with configurable on/off via chat template (`enable_thinking=True/False`) (official model card).
- Tool/function calling (official "Best For" lists tool use; fixture-reported, consistent across fixtures).
- Temperature control (fixture-reported, consistent across fixtures).
- Text in / text out (official model card: Input/Output Type Text).
- 262144 context on the free routes (Kilo and Kenari live catalogs); the model itself supports up to 1M tokens with a 256K default HF configuration (official model card — see Notes).
- Open weights (checkpoints on Hugging Face: BF16/FP8/NVFP4) under the NVIDIA Nemotron Open Model License.

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Kilo Code](../providers/kilo-code.md) | `nvidia/nemotron-3-super-120b-a12b:free` | Standing `:free` lane; anonymous keyless access allowed, no account/key/card | None published combo-specific; provider-wide anonymous `:free` quota applies (see provider file); roster rotates | 2026-09-05 |
| [OpenRouter](../providers/openrouter.md) | `nvidia/nemotron-3-super-120b-a12b:free` | Permanent `:free` variant; account + key, no card | None published combo-specific; provider-wide free-model caps apply (see provider file); roster rotates | 2026-09-05 |
| [Kenari](../providers/kenari.md) | `nemotron-3-super-120b-a12b:free` | `:free` lane billed Rp 0 (live-catalog-observed 2026-09-05); account + key (`kn-...`), no top-up | None published combo-specific; per-minute caps + tiered daily quotas apply (see provider file); confirm via `GET /v1/models` before use | 2026-09-05 |
| [Requesty](../providers/requesty.md) | `nvidia/nemotron-3-super-120b-a12b` | Free-models tier ("free for now"); account + key, no card | New orgs: 200 req/day + 20 req/min shared across all free models combined | 2026-09-05 |
| [FastRouter](../providers/fastrouter.md) | `nvidia/nemotron-3-super:free` | ⚠ `:free` lane; org must hold a paid credit balance above $1 or free calls 402 | 10 req/day per org per model, UTC-midnight reset | 2026-09-05 |

**Notes:**

- Context discrepancy: the official model card states up to 1M tokens (default/HF configuration 256K); the Kilo and Kenari free-route catalogs both serve it at 262144 — card default follows the as-served free-route figure.
- Sibling distinction: Nano (30B total / 3B active) has its own card ([nemotron-3-nano-30b-a3b.md](nemotron-3-nano-30b-a3b.md)); Ultra (550B/A55B) and 3.5 variants are separate models — split into their own cards if their availability diverges.
- `max_output_tokens`: no official figure found — omitted.
- Knowledge cutoff: no official date found — omitted.
- Structured output: fixtures disagree (present on OpenRouter fixture, absent on Kilo fixture) — omitted.

**Sources**

- https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b/modelcard (official: 120B/12B, LatentMoE Mamba-2 hybrid + MTP, reasoning flag, tool use, 1M max / 256K default context, text in/out, license, 2026-03-11 release)
- https://research.nvidia.com/labs/nemotron/Nemotron-3-Super/ (official: 12B-active/120B-total MoE, 1M context)
- https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16 (weights, license)
- https://api.kilo.ai/api/gateway/models (live catalog: `:free` row, 262144 context — free-route figure)
- https://openrouter.ai/api/v1/models (live `:free` roster)
- https://kenari.id/v1/models (live catalog queried 2026-09-05: `:free` ID with `"free": true` — free-route figure)
- raw/opencode-models-api/kilo/model_nemotron-3-super-120b-a12b:free.json (capabilities/modalities — fixture-reported, discovery only)
- raw/opencode-models-api/openrouter/model_nemotron-3-super-120b-a12b:free.json (capabilities/modalities — fixture-reported, discovery only)
