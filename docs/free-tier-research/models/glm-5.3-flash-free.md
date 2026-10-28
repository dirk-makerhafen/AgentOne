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
  input: [text, image, video]
  output: [text]
open_weights: true
providers:
  - name: OpenCode Zen
    file: opencode-zen
    model_id: glm-5.3-flash-free
    conditions: "Anonymous free pool; no account, key, or payment; limited-time free (feedback-collection period)"
    verified: "2026-10-28"
  - name: OpenRouter
    file: openrouter
    model_id: zhipuai/glm-5.3-flash:free
    conditions: "Permanent `:free` variant; account + key, no card; free-model caps apply account-wide; roster rotates"
    verified: "2026-10-28"
  - name: Kilo Code
    file: kilo-code
    model_id: zhipuai/glm-5.3-flash:free
    conditions: "Standing `:free` lane; anonymous keyless access allowed, no account/key/card; roster rotates"
    verified: "2026-10-28"
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

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [OpenCode Zen](../providers/opencode-zen.md) | `glm-5.3-flash-free` | Anonymous free pool; no account, key, or payment; limited-time free | No published numbers; free-pool enforced via `FreeUsageLimitError` | 2026-10-28 |
| [OpenRouter](../providers/openrouter.md) | `zhipuai/glm-5.3-flash:free` | Permanent `:free` variant; account + key, no card | Provider-wide free-model caps apply; roster rotates | 2026-10-28 |
| [Kilo Code](../providers/kilo-code.md) | `zhipuai/glm-5.3-flash:free` | Standing `:free` lane; anonymous keyless access allowed | Provider-wide anonymous `:free` quota applies; roster rotates | 2026-10-28 |

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