---
name: Kimi K3
developer: Moonshot AI
canonical_id: moonshot-ai/kimi-k3
leaderboard_id: kimi-k3
leaderboard_rank: 9
family: kimi
context_window: 1048576
reasoning: true
tool_call: true
modalities:
  input: [text, image, video]
  output: [text]
open_weights: true
providers:
  - name: Pollinations.ai
    file: pollinations
    model_id: kimi-k3
    conditions: "Quest-earned Pollen; account + key (sk_); zero-Pollen-priced models free"
    verified: "2026-09-05"
---

Kimi K3 is Moonshot AI's flagship open-weight agentic model (2.8T-parameter MoE, 16 of 896 experts active) for long-horizon coding, knowledge work, and deep reasoning, with a 1M-token context window and always-on thinking mode (official platform docs).

**Capabilities:**

- Always-on reasoning ("thinking mode") with configurable reasoning effort, tool/function calling, and JSON mode (official platform docs).
- Native visual understanding; text, image, and video input with text output (official quickstart).
- Open weights (MoonshotAI/Kimi-K3 on GitHub, XiaomiMiMo-style HF release under the Kimi K3 License track — verify license text at release before commercial use).
- OpenAI-compatible Chat Completions plus Responses and Anthropic Messages endpoints on the official API.

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Pollinations.ai](../providers/pollinations.md) | `kimi-k3` | Quest-earned Pollen; account + key (`sk_`); zero-Pollen-priced models free | No published RPM figures; binding constraints are Pollen balance and per-key budgets | 2026-09-05 |

**Notes:**

- LLM7 lists `kimi-k3` but its live catalog tiers it as `pro` (NOT free) as of 2026-09-05 — not a free row, excluded.
- Ollama Cloud lists `kimi-k3` at $3.00/$15.00 per 1M with an unlabeled starter-model subset — not claimed as a free row (confirm starter status live before use).
- `max_output_tokens`: third-party catalogs disagree (32,768 vs 1M) and no official per-request max confirmed — omitted.
- Official model ID on Moonshot's own API is `kimi-k3` (`https://api.moonshot.ai/v1`); Kimi Code uses the short alias `k3` — do not confuse them.
- Weights release was scheduled by July 27, 2026 with weights reported released that week; confirm the final license file before self-hosting.

**Sources**

- https://platform.kimi.ai/docs/guide/kimi-k3-quickstart (official: 2.8T params, KDA + Attention Residuals, 1M context, native vision, open-source 3T-class)
- https://platform.kimi.ai/docs/overview (official: kimi-k3, 1M context, text/image/video input, tool calls)
- https://platform.kimi.ai/docs/api/overview (official: base URLs, protocol compatibility)
- https://platform.kimi.ai/docs/guide/kimi-k3-tool-calling-best-practice (official: tool calling, reasoning effort)
- https://github.com/MoonshotAI/Kimi-K3 (official weights repo)
- raw/opencode-models-api/ discovery data (leads only, not authoritative)
