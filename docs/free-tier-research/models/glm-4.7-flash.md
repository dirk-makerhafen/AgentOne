---
name: GLM-4.7-Flash
developer: Zhipu AI (Z.AI)
canonical_id: z-ai/glm-4.7-flash
leaderboard_id: glm-4.7-flash
leaderboard_rank: 178
family: glm-flash
context_window: 200000
reasoning: true
tool_call: true
temperature: true
modalities:
  input:
  - text
  output:
  - text
open_weights: true
knowledge_cutoff: 2025-04
---

GLM-4.7-Flash is Z.AI's efficient reasoning/coding model with a permanent zero-price API tier (context ≈200K per secondary data; verify live).

**Capabilities:**

- Reasoning, tool/function calling, temperature control (fixture-reported).
- Text in / text out; ~200K context (secondary data, verify live).
- Open weights.

**Notes:**

- Do not confuse with `glm-4.7-flashx` (paid FlashX lane) or the GLM Coding Plan subscription (separate product/endpoints, from $18/mo).
- KUAE Cloud's $0 GLM-4.7 row is a 30-day trial, not a standing tier — excluded.
- ZenMux runs a standing free lane for `z-ai/glm-4.7-flash-free` at $0/token (verified live 2026-09-06). Earlier iterations had ZenMux `$0` rows gated behind a paid plan — the free roster rotates, so re-check https://zenmux.ai/models before relying on it; nothing here documents a paid-plan-free combination anymore.
- Hugging Face `zai-org/GLM-4.7-Flash` is paid per token (draws from the $0.10/mo credit pool; fixture cost-0 rows are artifacts) — excluded.
- MegaNova `zai-org/GLM-4.7-Flash` has Tier 1 quota 0 and needs a Tier 2 $1 deposit — excluded as a free row.

**Sources**

- https://docs.z.ai/guides/overview/pricing
- https://docs.z.ai/devpack/overview (coding-plan separation)
- https://aihubmix.com/models/free (56-lane, 10 trial calls, $1 top-up → daily quotas)
