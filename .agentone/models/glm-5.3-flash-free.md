---
name: GLM-5.3-Flash Free
developer: Zhipu AI
canonical_id: zhipuai/glm-5.3-flash
leaderboard_id: glm-5.3-flash-free
leaderboard_rank: 134
family: glm-flash
context_window: 200000
reasoning: true
tool_call: true
temperature: true
modalities:
  input:
  - text
  - image
  - video
  output:
  - text
open_weights: true
---

GLM-5.3-Flash is Zhipu AI's native multimodal flash-tier model in the GLM-5 generation, designed for efficient coding and long-horizon agent tasks with vision and video understanding.

**Capabilities:**

- Native multimodal: text, image, and video input with text output
- Reasoning with configurable effort levels (low, high, max)
- Tool/function calling support
- Structured output support
- Temperature control
- 200K context window, 32K max output
- Open weights (Zhipu AI GLM release)
- Optimized for coding and long-horizon agent tasks

**Notes:**

- Release date: 2026-08-26
- Canonical model: `zhipuai/glm-5.3-flash`
- Part of GLM-5 generation (flash tier = efficiency optimized)
- Free on OpenCode Zen via the inference endpoint `https://opencode.ai/inference/openai/v1`
- Distinct from GLM-4 series and earlier generations

**Sources**

- https://huggingface.co/ZhipuAI/GLM-5.3-Flash (official weights)
- https://opencode.ai/zen/v1/models (live catalog)
- ../providers/opencode-zen.md (verified 2026-10-28)
- ../providers/openrouter.md (roster 2026-10-28)
- ../providers/kilo-code.md (catalog 2026-10-28)
- https://www.zhipuai.cn/ (Zhipu AI official site)
