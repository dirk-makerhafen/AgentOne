---
name: Nemotron 3 Ultra 550B A55B
developer: Nvidia
canonical_id: nvidia/nemotron-3-ultra-550b-a55b
leaderboard_id: nemotron-3-ultra-550b-a55b
leaderboard_rank: 72
family: nemotron
context_window: 1048576
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
    model_id: nvidia/nemotron-3-ultra-550b-a55b:free
    conditions: "Standing `:free` lane; anonymous keyless access allowed, no account/key/card; roster rotates"
    verified: "2026-09-05"
  - name: OpenRouter
    file: openrouter
    model_id: nvidia/nemotron-3-ultra-550b-a55b:free
    conditions: "Permanent `:free` variant; account + key, no card; free-model caps apply account-wide; roster rotates"
    verified: "2026-09-05"
  - name: Kenari
    file: kenari
    model_id: nemotron-3-ultra-550b-a55b:free
    conditions: "`:free` lane billed Rp 0 (live-catalog-observed 2026-09-05); account + key (`kn-...`), no top-up; confirm via GET /v1/models"
    verified: "2026-09-05"
  - name: OpenCode Zen
    file: opencode-zen
    model_id: nemotron-3-ultra-free
    conditions: "Anonymous free pool; no account, key, or payment; limited-time free (feedback-collection period)"
    verified: "2026-09-05"
  - name: Requesty
    file: requesty
    model_id: nvidia/nemotron-3-ultra-550b-a55b
    conditions: "Free-models tier ('free for now'); account + key, no card; quota shared across all free models combined"
    limits:
      requests:
        minute: 20
        day: 200
    verified: "2026-09-05"
---

Nemotron 3 Ultra 550B A55B is Nvidia's largest Nemotron 3 model: a frontier-scale hybrid MoE (550B total / 55B active, LatentMoE Mamba-2 + MoE + Attention with Multi-Token Prediction) for complex multi-step agents, long-context analysis, and high-accuracy reasoning over code, math, and science. It is the Ultra sibling of the Nemotron 3 family — not the Super model ([Nemotron 3 Super 120B A12B](nemotron-3-super-120b-a12b.md)) nor the Nano model ([Nemotron 3 Nano 30B A3B](nemotron-3-nano-30b-a3b.md)).

**Capabilities:**

- Reasoning trace with configurable on/off via chat template (`enable_thinking=True/False`, plus medium-effort and budget-controlled modes) (official model card).
- Tool/function calling (official "Best For" lists tool use; vLLM/SGLang serve recipes use the `qwen3_coder` tool-call parser).
- Temperature control (official API examples use temperature 1.0 / top_p 0.95).
- Text in / text out (official model card: Input/Output Type Text).
- Up to 1M context (official model card; NIM serves 262144 natively, extendable to 1048576; Kilo and Kenari free routes list 1M).
- Open weights (BF16 and NVFP4 checkpoints on Hugging Face) under the OpenMDW License Agreement v1.1.

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Kilo Code](../providers/kilo-code.md) | `nvidia/nemotron-3-ultra-550b-a55b:free` | Standing `:free` lane; anonymous keyless access allowed, no account/key/card | None published combo-specific; provider-wide anonymous `:free` quota applies (see provider file); roster rotates | 2026-09-05 |
| [OpenRouter](../providers/openrouter.md) | `nvidia/nemotron-3-ultra-550b-a55b:free` | Permanent `:free` variant; account + key, no card | None published combo-specific; provider-wide free-model caps apply (see provider file); roster rotates | 2026-09-05 |
| [Kenari](../providers/kenari.md) | `nemotron-3-ultra-550b-a55b:free` | `:free` lane billed Rp 0 (live-catalog-observed 2026-09-05); account + key (`kn-...`), no top-up | None published combo-specific; per-minute caps + tiered daily quotas apply (see provider file); confirm via `GET /v1/models` before use | 2026-09-05 |
| [OpenCode Zen](../providers/opencode-zen.md) | `nemotron-3-ultra-free` | Anonymous free pool; no account, key, or payment; limited-time free | None published; free pool enforced via `FreeUsageLimitError` (quota and reset window unknown) | 2026-09-05 |
| [Requesty](../providers/requesty.md) | `nvidia/nemotron-3-ultra-550b-a55b` | Free-models tier ("free for now"); account + key, no card | New orgs: 200 req/day + 20 req/min shared across all free models combined | 2026-09-05 |

**Notes:**

- Context: the official model card states up to 1M tokens; NIM's native serving default is 262144 (extendable to 1M). The Kilo and Kenari free-route catalogs both list 1M — card default follows the official maximum, which matches the as-served free routes.
- Sibling distinction: Super (120B total / 12B active) and Nano (30B total / 3B active) have their own cards; 3.5-generation variants (Lightning, Content Safety) are separate models with their own cards.
- `max_output_tokens`: no official figure found — omitted.
- Knowledge cutoff: official docs give two dates (pre-training September 2025, post-training May 2026) with no single cutoff — omitted.
- Free-route data handling: NVIDIA free endpoints are trial-use only with session logging under NVIDIA API Trial Terms — do not submit personal or confidential data on free routes.

**Sources**

- https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16 (official: 550B/55B, LatentMoE Mamba-2 hybrid + MTP, reasoning flag, tool use, 1M context, text in/out, OpenMDW-1.1, 2026-06-04 release, cutoffs)
- https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b/modelcard (official model card mirror)
- https://research.nvidia.com/labs/nemotron/Nemotron-3-Ultra/ (official: 55B-active/550B-total MoE)
- https://docs.nvidia.com/nim/large-language-models/2.0.6/day-0/get-started-nemotron-3-ultra.html (official NIM docs: 262144 native default, extendable to 1M)
- https://developer.nvidia.com/topics/ai/nemotron (official family overview)
- ../providers/kilo-code.md (`nvidia/nemotron-3-ultra-550b-a55b:free`, 1M context — live catalog 2026-09-05)
- ../providers/openrouter.md (`nvidia/nemotron-3-ultra-550b-a55b:free` — live roster 2026-09-05)
- ../providers/kenari.md (`nemotron-3-ultra-550b-a55b:free`, 1M context — live catalog 2026-09-05)
- ../providers/opencode-zen.md (`nemotron-3-ultra-free` — verified working anonymously 2026-09-05)
- ../providers/requesty.md (`nvidia/nemotron-3-ultra-550b-a55b` free input/output — free-models doc 2026-09-05)
