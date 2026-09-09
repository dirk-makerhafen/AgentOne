---
name: MiniMax M2.7
developer: MiniMax
canonical_id: minimax/minimax-m2.7
leaderboard_id: minimax-m2.7
leaderboard_rank: 105
family: minimax
context_window: 204800
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
    model_id: minimax/minimax-m2.7:free
    conditions: "Standing `:free` lane; anonymous keyless access allowed, no account/key/card; roster rotates"
    verified: "2026-09-05"
  - name: OpenRouter
    file: openrouter
    model_id: minimax/minimax-m2.7:free
    conditions: "Permanent `:free` variant; account + key, no card; free-model caps apply account-wide; roster rotates"
    verified: "2026-09-05"
  - name: LLM7.io
    file: llm7
    model_id: minimax-m2.7
    conditions: "Live-verified free `turbo` ID; anonymous with `api_key=\"unused\"` or free token; `turbo` roster rotates"
    verified: "2026-09-05"
  - name: AIHubMix
    file: aihubmix
    model_id: minimax-m2.7-free
    conditions: "Free-model lane; account + key, no card; trial-use, 429s possible under load"
    verified: "2026-09-05"
---

MiniMax M2.7 is MiniMax's agentic coding/productivity model (MoE, ~230B total / ~10B active) with tool calling, Agent Teams, and dynamic tool search. Official context window is 204800; free-route catalogs report lower figures (see Notes).

**Capabilities:**

- Reasoning and tool/function calling (official tool-calling guide; fixture-reported, consistent with official announcement describing system-level reasoning).
- Temperature control (fixture-reported, consistent across fixtures).
- Text in / text out (fixture-reported, consistent with NVIDIA NIM reference listing Text input); image/video input unverified — omitted.
- Open weights (weights on Hugging Face/GitHub/ModelScope) under a custom non-commercial license — commercial use requires prior written authorization (see Notes).

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Kilo Code](../providers/kilo-code.md) | `minimax/minimax-m2.7:free` | Standing `:free` lane; anonymous keyless access allowed, no account/key/card | None published combo-specific; provider-wide anonymous `:free` quota applies (see provider file); roster rotates | 2026-09-05 |
| [OpenRouter](../providers/openrouter.md) | `minimax/minimax-m2.7:free` | Permanent `:free` variant; account + key, no card | None published combo-specific; provider-wide free-model caps apply (see provider file); roster rotates | 2026-09-05 |
| [LLM7.io](../providers/llm7.md) | `minimax-m2.7` | Live-verified free `turbo` ID; anonymous with `api_key="unused"` or free token | None published combo-specific; provider-wide Anonymous/Free-token quotas apply (see provider file); `turbo` roster rotates | 2026-09-05 |
| [AIHubMix](../providers/aihubmix.md) | `minimax-m2.7-free` | Free-model lane; account + key, no card | None published; free versions are trial-use (limited resources, 429s possible under load) | 2026-09-05 |

**Notes:**

- Context discrepancy: official MiniMax API docs list M2.7 at 204800; the Kilo live catalog row reports 196608 and fixtures disagree on max output (131072 vs 196608) — card default follows the official 204800; `max_output_tokens` omitted as unverifiable.
- License: Hugging Face tags the repo `license: other`; the repo LICENSE is a non-commercial license (commercial use requires prior written authorization from MiniMax, prohibited use categories) — not Apache/MIT. Verify the exact checkpoint license before commercial use.
- Knowledge cutoff: no official date found — omitted.
- Structured output: fixtures disagree (present on OpenRouter fixture, absent on Kilo fixture) — omitted.
- Skipped leads: StreamLake Vanchin lists `MiniMax-M2.7` as a representative base model but maps base models to per-user endpoint IDs with login-gated free eligibility — no 1:1 free ID assertable. Pollinations snapshots a textually identical `minimax-m2.7` ID, but its provider file documents only that zero-Pollen pricing (resolved live per model) constitutes free — the snapshot asserts no price, so free status is unverified (re-verification lead: check `GET /v1/models`).

**Sources**

- https://platform.minimax.io/docs/guides/text-generation (official: M2.7 context window 204800)
- https://github.com/MiniMax-AI/MiniMax-M2.7 (official: weights, agent/coding positioning)
- https://github.com/MiniMax-AI/MiniMax-M2.7/blob/main/docs/tool_calling_guide.md (official: tool-calling support and syntax)
- https://www.minimax.io/news/minimax-m27-en (official announcement: reasoning, Agent Teams, tool/skill use)
- https://huggingface.co/MiniMaxAI/MiniMax-M2.7 (weights, `license: other`, custom non-commercial LICENSE)
- https://docs.api.nvidia.com/nim/re/reference/minimaxai-minimax-m2.7 (Text input, ISL 204800, MoE 230B/10B)
- https://api.kilo.ai/api/gateway/models (live catalog: `:free` row with 196608 context — free-route figure)
- https://openrouter.ai/api/v1/models (live `:free` roster)
- https://api.llm7.io/v1/models (live catalog: `minimax-m2.7` as `turbo`/free ID)
- raw/opencode-models-api/kilo/model_minimax-m2.7.json (capabilities/context/modalities — fixture-reported, discovery only)
- raw/opencode-models-api/openrouter/model_minimax-m2.7.json (capabilities/context/modalities — fixture-reported, discovery only)
