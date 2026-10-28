---
name: MiMo-V2.6-Flash Free
developer: Xiaomi
canonical_id: xiaomi/mimo-v2.6-flash
leaderboard_id: mimo-v2.6-flash-free
leaderboard_rank: 112
family: mimo
context_window: 200000
reasoning: true
tool_call: true
temperature: true
modalities:
  input: [text, image, audio, video]
  output: [text]
open_weights: true
providers:
  - name: OpenCode Zen
    file: opencode-zen
    model_id: mimo-v2.6-flash-free
    conditions: "Anonymous free pool; no account, key, or payment; limited-time free (feedback-collection period)"
    verified: "2026-10-28"
---

MiMo-V2.6-Flash is Xiaomi's latest flash-tier multimodal model in the MiMo series, designed for multimodal coding agents and long-context automation. It is a smaller, faster variant of the MiMo-V2.6 family.

**Capabilities:**

- Native multimodal: text, image, audio, and video input with text output
- Reasoning capabilities (toggle-based)
- Tool/function calling support
- Temperature control
- 200K context window, 32K max output
- Open weights (Xiaomi MiMo release)
- Optimized for coding agents and long-context automation

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [OpenCode Zen](../providers/opencode-zen.md) | `mimo-v2.6-flash-free` | Anonymous free pool; no account, key, or payment; limited-time free | No published numbers; free-pool enforced via `FreeUsageLimitError` | 2026-10-28 |

**Notes:**

- Release date: 2026-09-22
- Canonical model: `xiaomi/mimo-v2.6-flash`
- Part of the MiMo-V2.6 family (flash tier)
- Free on OpenCode Zen via the inference endpoint `https://opencode.ai/inference/openai/v1`
- Do not confuse with MiMo-V2.5 (different architecture generation)

**Sources**

- https://mimo.xiaomi.com (official Xiaomi MiMo site)
- https://opencode.ai/zen/v1/models (live catalog)
- ../providers/opencode-zen.md (verified 2026-10-28)