---
name: North Mini Code
developer: Cohere
canonical_id: cohere/north-mini-code
leaderboard_id: north-mini-code-1.0
leaderboard_rank: 256
family: north
context_window: 256000
max_output_tokens: 64000
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
    model_id: cohere/north-mini-code:free
    conditions: "Standing `:free` lane; anonymous keyless access allowed, no account/key/card; code-specialized, 256K context; roster rotates"
    verified: "2026-09-05"
  - name: OpenRouter
    file: openrouter
    model_id: cohere/north-mini-code:free
    conditions: "Permanent `:free` variant; account + key, no card; free-model caps apply account-wide; roster rotates"
    verified: "2026-09-05"
---

North Mini Code is Cohere's open-weights agentic coding model: a 30B-total / 3B-active sparse MoE (128 experts, 8 active per token) trained for code generation, agentic software engineering, and terminal tasks, released under Apache 2.0.

**Capabilities:**

- Code-specialized: agentic software engineering (repo-level changes in harnesses like SWE-Agent and OpenCode), terminal-based agents, local/on-device coding (official blog and docs).
- Interleaved thinking / reasoning (official Hugging Face config; fixture-reported, consistent across fixtures).
- Tool/function calling (official docs page lists tool use; fixture-reported, consistent across fixtures).
- Temperature control (fixture-reported, consistent across fixtures).
- Text in / text out (official Hugging Face model card: "Input: Text only. Output: Model generates text.").
- 256K total context, 64K max generation (official blog and Hugging Face model card).
- Open weights under Apache 2.0 (Hugging Face, BF16/FP8/NVFP4 checkpoints).

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Kilo Code](../providers/kilo-code.md) | `cohere/north-mini-code:free` | Standing `:free` lane; anonymous keyless access allowed, no account/key/card | None published combo-specific; provider-wide anonymous `:free` quota applies (see provider file); roster rotates | 2026-09-05 |
| [OpenRouter](../providers/openrouter.md) | `cohere/north-mini-code:free` | Permanent `:free` variant; account + key, no card | None published combo-specific; provider-wide free-model caps apply (see provider file); roster rotates | 2026-09-05 |

**Notes:**

- Cohere's own API serves North Mini Code paid/trial-only (Trial keys: 20 req/min, 1,000 calls/month, not for production — see [Cohere](../providers/cohere.md)); the free rows above are the routers' `:free` lanes, not Cohere itself.
- Knowledge cutoff: no official date found — omitted.
- Structured output: fixtures disagree (absent on OpenRouter fixture, present on Cohere fixture) — omitted.

**Sources**

- https://cohere.com/blog/north-mini-code (official: 30B total / 3B active MoE, Apache 2.0, 256K context / 64K max generation, agentic-coding positioning)
- https://cohere.com/north-mini-code (official: 256K context, Apache 2.0, 30B total / 3B active)
- https://huggingface.co/CohereLabs/North-Mini-Code-1.0 (official model card: text in/out, MoE architecture, 256K context / 64K output, Apache 2.0)
- https://huggingface.co/blog/CohereLabs/introducing-north-mini-code (official: agentic-coding training, tool use)
- https://github.com/cohere-ai/cohere-developer-experience/blob/main/fern/pages/models/north/north-mini-code-1.0.mdx (official docs: tool use, SWE-Agent/OpenCode harnesses)
- https://api.kilo.ai/api/gateway/models (live catalog: `:free` row, 256K context — free-route figure)
- https://openrouter.ai/api/v1/models (live `:free` roster)
- raw/opencode-models-api/openrouter/model_north-mini-code:free.json (capabilities/modalities — fixture-reported, discovery only)
- raw/opencode-models-api/cohere/model_north-mini-code-1-0.json (capabilities/modalities — fixture-reported, discovery only)
