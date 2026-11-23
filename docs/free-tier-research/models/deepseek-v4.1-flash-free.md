---
name: DeepSeek V4.1 Flash Free
developer: DeepSeek
canonical_id: deepseek/deepseek-v4.1-flash
leaderboard_id: deepseek-v4.1-flash-free
leaderboard_rank: 76
family: deepseek-flash
context_window: 200000
reasoning: true
tool_call: true
temperature: true
modalities:
  input:
  - text
  - image
  output:
  - text
open_weights: true
---

DeepSeek V4.1 Flash is the flash-tier (efficiency) model in DeepSeek's V4 generation, designed for reasoning and agentic coding with multimodal capabilities.

**Capabilities:**

- Reasoning with toggle + effort levels (low, high, max)
- Tool/function calling support
- Structured output support
- Temperature control
- Multimodal: text and image input, text output
- 200K context window, 32K max output
- Open weights (DeepSeek release)
- Knowledge cutoff: 2025-05
- Part of DeepSeek V4.1 family (distinct from V3 and R1 families)

**Notes:**

- Release date: 2026-09-10
- Canonical model: `deepseek/deepseek-v4.1-flash`
- Free on OpenCode Zen via the inference endpoint `https://opencode.ai/inference/openai/v1`
- Distinct from DeepSeek-V3 (Mixture-of-Experts) and DeepSeek-R1 (reasoning) families
- Flash tier = optimized for speed/efficiency

**Sources**

- https://huggingface.co/deepseek/DeepSeek-V4.1-Flash (official weights)
- https://opencode.ai/zen/v1/models (live catalog)
- ../providers/opencode-zen.md (verified 2026-10-28)
- ../providers/openrouter.md (roster 2026-10-28)
- ../providers/kilo-code.md (catalog 2026-10-28)
