---
name: Xiaomi MiMo-V2.5
developer: Xiaomi
canonical_id: xiaomi/mimo-v2.5
leaderboard_id: mimo-v2.5
leaderboard_rank: 94
family: mimo
context_window: 1048576
reasoning: true
tool_call: true
modalities:
  input:
  - text
  - image
  - video
  - audio
  output:
  - text
open_weights: true
---

MiMo-V2.5 is Xiaomi's open-weight omnimodal agentic model (310B-parameter sparse MoE, 15B active, trained on 48T tokens) that sees, hears, and acts in one network, with a 1M-token context window (official release page).

**Capabilities:**

- Frontier-level agentic coding and multimodal reasoning (official: matches MiMo-V2.5-Pro at half the cost on MiMo Coding Bench; 62.3 on Claw-Eval general).
- Native visual and audio understanding across image, video, and multimodal agent tasks; text, image, video, and audio input with text output (official release page).
- Tool-use agentic workflows; 1M-token context progressively extended 32K → 256K → 1M during post-training (official release page).
- Fully open-sourced weights, tokenizer, and model card on Hugging Face (XiaomiMiMo/MiMo-V2.5, FP8 mixed precision; MIT license track per secondary sources — verify license file before commercial use).

**Notes:**

- ID naming: Kenari's `mimo-v2-5:free` (hyphens) and Zen's `mimo-v2.5-free` (dot) refer to the same Xiaomi MiMo-V2.5 family — Xiaomi's own release page lives at `mimo.xiaomi.com/mimo-v2-5` while the model is named MiMo-V2.5 and the instruct checkpoint is `XiaomiMiMo/MiMo-V2.5`. The difference is provider-side slug style, not a different model.
- Do not confuse with MiMo-V2.5-Pro (1.02T total / 42B active, text-focused flagship) — neither free lane serves the Pro variant.
- MiMo-V2.5-Base (256K context) vs MiMo-V2.5 instruct (1M context): card default is the 1M instruct figure.
- `max_output_tokens`: no official per-request max confirmed — omitted.
- Zen free-model data-may-be-used-for-training caveat applies to this row (see provider file).

**Sources**

- https://mimo.xiaomi.com/mimo-v2-5 (official: 310B/15B MoE, 48T tokens, 1M context, visual+audio, open-sourced, Hugging Face links)
- https://huggingface.co/XiaomiMiMo/MiMo-V2.5 (official weights)
- https://kenari.id/v1/models (live catalog, :free row with "free": true verified 2026-09-05)
- https://opencode.ai/zen/v1/models (live catalog verified 2026-09-05; anonymous probe returned free-pool limits, never a 401)
