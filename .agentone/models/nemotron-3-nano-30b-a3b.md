---
name: Nemotron 3 Nano 30B A3B
developer: Nvidia
canonical_id: nvidia/nemotron-3-nano-30b-a3b
leaderboard_id: nemotron-3-nano-30b-a3b
leaderboard_rank: 219
family: nemotron
context_window: 131072
reasoning: true
tool_call: true
temperature: true
modalities:
  input: [text]
  output: [text]
open_weights: true
providers:
  - name: Requesty
    file: requesty
    model_id: nvidia/nemotron-3-nano-30b-a3b
    conditions: "Free-models tier ('free for now'); account + key, no card; quota shared across all free models combined"
    limits:
      requests:
        minute: 20
        day: 200
    verified: "2026-09-05"
  - name: NVIDIA NIM
    file: nvidia-nim
    model_id: nvidia/nemotron-3-nano-30b-a3b
    conditions: "Free tier"
    verified: "2026-09-05"
  - name: FastRouter
    file: fastrouter
    model_id: nvidia/nemotron-3-nano-30b:free
    conditions: "⚠ `:free` lane (provider ID differs from card default); org must hold a paid credit balance above $1 or free calls 402"
    limits:
      requests:
        day: 10
    verified: "2026-09-05"
  - name: AIHubMix
    file: aihubmix
    model_id: nemotron-3-nano-30b-a3b-free
    conditions: "Free-model lane; account + key, no card; trial-use, 429s possible under load"
    verified: "2026-09-05"
---

Nemotron 3 Nano 30B A3B is Nvidia's small MoE for efficient coding, math, and long-context agents (fixture-reported facts; verify live).

**Capabilities:**

- Reasoning, tool/function calling, temperature control (fixture-reported).
- Text in / text out; ~131K context (fixture-reported).
- Open weights.

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Requesty](../providers/requesty.md) | `nvidia/nemotron-3-nano-30b-a3b` | Free-models tier ("free for now"); account + key, no card | New orgs: 200 req/day + 20 req/min shared across all free models combined | 2026-09-05 |
| [NVIDIA NIM](../providers/nvidia-nim.md) | `nvidia/nemotron-3-nano-30b-a3b` | Free tier ($0 fixture rows) | See provider file (catalog slugs churn) | 2026-09-05 |
| [FastRouter](../providers/fastrouter.md) | `nvidia/nemotron-3-nano-30b:free` | ⚠ `:free` lane (provider ID differs from card default); org must hold a paid credit balance above $1 or free calls 402 | 10 req/day per org per model, UTC-midnight reset | 2026-09-05 |
| [AIHubMix](../providers/aihubmix.md) | `nemotron-3-nano-30b-a3b-free` | Free-model lane; account + key, no card | None published combo-specific; 10 trial calls total before top-up, then topped-up daily quotas apply (see provider file); trial-use 429s possible | 2026-09-05 |

**Notes:**

- Sibling `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` is also free on Requesty; larger Nemotron 3 siblings (Super 120B, Ultra 550B) have their own free rows there — split into separate cards if their availability diverges.
- Omni exclusion (verified 2026-09-05): the Kilo Code (`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`) and OpenRouter (same ID) free lanes were NOT added here because official NVIDIA docs confirm Omni is a distinct model, not a Nano variant — it is a multimodal (video/audio/image/text) perception sub-agent with its own model page, Hugging Face repo (`nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16`), and technical report (see Sources). It deserves its own card if cataloged.

**Sources**

- raw/opencode-models-api/nvidia/model_nemotron-3-nano-30b-a3b.json (capabilities/context — discovery data)
- https://docs.requesty.ai/features/free-models
- https://fastrouter.ai/models?order=newest
- ../providers/aihubmix.md (`nemotron-3-nano-30b-a3b-free`, 256K context, 100/day · 10/min topped-up — free page verified 2026-09-05)
- https://developer.nvidia.com/topics/ai/nemotron (official: Nano Omni 30B A3B is a separate multimodal video/audio/image/text model vs Nano 30B A3B for coding/reasoning/math — Omni exclusion evidence)
- https://build.nvidia.com/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning (official: Omni has its own NIM page — Omni exclusion evidence)
