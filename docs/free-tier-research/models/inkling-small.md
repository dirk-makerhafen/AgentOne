---
name: Thinking Machines Inkling Small
developer: Thinking Machines Lab
canonical_id: thinkingmachines/inkling-small
family: inkling
leaderboard_id: inkling-small
leaderboard_rank: 64
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
    model_id: thinkingmachines/inkling-small:free
    conditions: "Standing `:free` lane; anonymous keyless access allowed, no account/key/card; roster rotates"
    verified: "2026-09-05"
  - name: OpenRouter
    file: openrouter
    model_id: thinkingmachines/inkling-small:free
    conditions: "Permanent `:free` variant; account + key, no card; free-model caps apply account-wide; roster rotates"
    verified: "2026-09-05"
---

Inkling Small is Thinking Machines Lab's quarter-size open-weights multimodal Mixture-of-Experts model (276B total / 12B active MoE, 42-layer, same routing recipe), released Jul 30 2026 as a follow-up to the flagship Inkling, with comparable performance at lower cost/latency. Weights are openly available under Apache 2.0 and fine-tunable on the lab's Tinker platform. Full-size sibling: [Inkling](inkling.md) (975B/41B, separate leaderboard entry with its own free-availability rows).

**Capabilities:**

- Native multimodal input: text, image, and audio in; text out (official model card; trained on text, images, audio, video).
- Controllable thinking effort / reasoning (official announcements; effort sweeps minimal–xhigh; HLE/AIME/GPQA reasoning evals).
- Agentic and tool-use systems are an intended use (official model card); tool evals include HLE-with-tools, MCP Atlas, Toolathlon, Tau-3 Banking.
- Coding assistants and chatbots are intended uses (official model card; SWE-Bench Verified 80.2%, Terminal-Bench 2.1).
- 1M-token context window (official); router catalogs expose 1048576 (frontmatter uses the catalog value).
- Open weights under Apache 2.0 (official model card; BF16 plus MXFP8/NVFP4 checkpoints on Hugging Face).

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Kilo Code](../providers/kilo-code.md) | `thinkingmachines/inkling-small:free` | Standing `:free` lane; anonymous keyless access allowed | 200 req/hour per IP anonymous; authenticated free-model limits unpublished | 2026-09-05 |
| [OpenRouter](../providers/openrouter.md) | `thinkingmachines/inkling-small:free` | Free `:free` variant; account + key, no card | None combo-specific; provider-wide free-variant caps apply (see provider file) | 2026-09-05 |

**Notes:**

- Leaderboard aliases: the raw leaderboard CSV also contains the strings `Inkling Small` and `Inkling-Small` — these refer to this same model (`inkling-small`), not separate models; no extra files created.
- No `limits` in frontmatter: no combo-specific numerics are documented for this row; provider-wide defaults stay in the provider files.
- Knowledge cutoff: the official card states only "limited to information available as of its training cutoff" with no date — omitted.
- Max output tokens: no official figure found — omitted.
- Temperature / structured output: not verified against official sources — omitted.
- At launch the lab previewed Inkling-Small inside the Inkling announcement (12B active); the standalone Inkling-Small release followed Jul 30 2026.

**Sources**

- https://thinkingmachines.ai/news/inkling-small/ (official: 276B/12B MoE, 1M context, open weights)
- https://thinkingmachines.ai/news/introducing-inkling/ (official: Small preview with 12B active)
- https://thinkingmachines.ai/model-card/inkling-small/ (official: 42-layer MoE, input/output modalities, 1M context)
- https://huggingface.co/thinkingmachines/Inkling-Small (official weight repo, linked from model card)
- https://api.kilo.ai/api/gateway/models (live catalog: `:free` row, 1048576 context — free-route figure)
- https://openrouter.ai/api/v1/models (live `:free` roster)
