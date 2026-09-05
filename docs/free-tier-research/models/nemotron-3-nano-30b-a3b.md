---
name: Nemotron 3 Nano 30B A3B
developer: Nvidia
canonical_id: nvidia/nemotron-3-nano-30b-a3b
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

**Notes:**

- Sibling `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` is also free on Requesty; larger Nemotron 3 siblings (Super 120B, Ultra 550B) have their own free rows there — split into separate cards if their availability diverges.

**Sources**

- raw/opencode-models-api/nvidia/model_nemotron-3-nano-30b-a3b.json (capabilities/context — discovery data)
- https://docs.requesty.ai/features/free-models
