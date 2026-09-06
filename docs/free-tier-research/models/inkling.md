---
name: Thinking Machines Inkling
developer: Thinking Machines Lab
canonical_id: thinkingmachines/inkling
family: inkling
leaderboard_id: inkling
leaderboard_rank: 225
context_window: 1048576
reasoning: true
tool_call: true
modalities:
  input: [text, image, audio]
  output: [text]
open_weights: true
providers:
  - name: Kilo Code
    file: kilo-code
    model_id: thinkingmachines/inkling:free
    conditions: "Standing `:free` lane; anonymous keyless access allowed, no account/key/card; roster rotates"
    verified: "2026-09-05"
  - name: OpenRouter
    file: openrouter
    model_id: thinkingmachines/inkling:free
    conditions: "Permanent `:free` variant; account + key, no card; free-model caps apply account-wide; roster rotates"
    verified: "2026-09-05"
---

Inkling is Thinking Machines Lab's flagship open-weights multimodal Mixture-of-Experts model (975B total / 41B active MoE: 66-layer, 256 experts, 6 routed + 2 shared per token), released Jul 15 2026. Weights are openly available under Apache 2.0 and fine-tunable on the lab's Tinker platform. Smaller sibling: [Inkling Small](inkling-small.md) (276B/12B, separate leaderboard entry with its own free-availability rows).

**Capabilities:**

- Native multimodal input: text, image, and audio in; text out (official model card; trained on text, images, audio, video).
- Controllable thinking effort / reasoning (official announcement; effort sweeps minimal–xhigh; HLE/AIME/GPQA reasoning evals).
- Agentic and tool-use systems are an intended use (official model card); tool evals include HLE-with-tools, MCP Atlas, Toolathlon, Tau-3 Banking.
- Coding assistants and chatbots are intended uses (official model card; SWE-Bench Verified 77.6%, Terminal-Bench 2.1).
- 1M-token context window (official); router catalogs expose 1048576 (frontmatter uses the catalog value).
- Open weights under Apache 2.0 (official model card; BF16 plus MXFP8/NVFP4 checkpoints on Hugging Face).

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Kilo Code](../providers/kilo-code.md) | `thinkingmachines/inkling:free` | Standing `:free` lane; anonymous keyless access allowed | 200 req/hour per IP anonymous; authenticated free-model limits unpublished | 2026-09-05 |
| [OpenRouter](../providers/openrouter.md) | `thinkingmachines/inkling:free` | Free `:free` variant; account + key, no card | None combo-specific; provider-wide free-variant caps apply (see provider file) | 2026-09-05 |

**Notes:**

- No `limits` in frontmatter: no combo-specific numerics are documented for this row; provider-wide defaults stay in the provider files.
- Knowledge cutoff: the official card states only "limited to information available as of its training cutoff" with no date — omitted.
- Max output tokens: no official figure found — omitted.
- Temperature / structured output: not verified against official sources — omitted.

**Sources**

- https://thinkingmachines.ai/news/introducing-inkling/ (official: 975B/41B MoE, 1M context, 45T multimodal tokens, open weights, Small preview)
- https://thinkingmachines.ai/model-card/inkling/ (official: Apache 2.0, text/image/audio in, text out, agentic/tool-use intended uses, evals)
- https://huggingface.co/thinkingmachines/inkling (official weight repo, linked from model card)
- https://api.kilo.ai/api/gateway/models (live catalog: `:free` row, 1048576 context — free-route figure)
- https://openrouter.ai/api/v1/models (live `:free` roster)
