---
name: Step 3.7 Flash
developer: StepFun
canonical_id: stepfun/step-3.7-flash
leaderboard_rank_estimated: "~60"
family: step
context_window: 262144
reasoning: true
tool_call: true
modalities:
  input: [text, image, video]
  output: [text]
open_weights: true
providers:
  - name: Kilo Code
    file: kilo-code
    model_id: stepfun/step-3.7-flash:free
    conditions: "Standing :free lane at $0 prompt/completion; anonymous, no key, no card"
    verified: "2026-09-05"
  - name: Kenari
    file: kenari
    model_id: step-3-7-flash:free
    conditions: ":free lane billed Rp 0, best-effort; account + key (kn-...), no top-up"
    verified: "2026-09-05"
---

Step 3.7 Flash is StepFun's high-efficiency multimodal MoE model (198B total / ~11B active params) for agentic coding, tool use, and long-context reasoning, with native image and video understanding and three reasoning-effort levels (official platform docs).

**Capabilities:**

- Sparse MoE (198B total / 11B activated) with high-throughput reasoning; `low` / `medium` / `high` reasoning effort control (official docs).
- Native image and video understanding; text, image, and video input with text output (official docs).
- Reliable `tools` / `tool_choice` orchestration for multi-step agent tasks (official docs).
- Open weights (stepfun-ai/Step-3.7-Flash on Hugging Face and GitHub; Apache 2.0 track per secondary sources — verify license file before commercial use).

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Kilo Code](../providers/kilo-code.md) | `stepfun/step-3.7-flash:free` | Standing `:free` lane at $0 prompt/completion; anonymous, no key, no card | Anonymous 200 req/hour per IP (provider-wide); roster rotates, verify live | 2026-09-05 |
| [Kenari](../providers/kenari.md) | `step-3-7-flash:free` | `:free` lane billed Rp 0, best-effort; account + key (`kn-...`), no top-up | Per-minute cap plus tiered daily quotas, operator-set (see provider file) | 2026-09-05 |

**Notes:**

- Context: official StepFun docs state "256K tokens"; third-party catalogs list 262144 (256K). Card default is 262144, matching both free providers' catalog figures (Kilo 262K, Kenari 262K).
- `max_output_tokens`: no official per-request max confirmed — omitted.
- Kenari's non-suffixed `step-3-7-flash` (if seen in fixtures) is metered — only the `:free`-suffixed ID is Rp 0.
- `leaderboard_rank_estimated: "~60"` (2026-09-05): no `leaderboard.csv` entry for step-3.7-flash (absent from the 2026-09-06 CSV refresh). Basis: successor to step-3.5-flash (CSV rank 67); independent third-party aggregates put step-3.7-flash above that predecessor (ModelCap top-44 of 236, BenchAlign ~111/231, SWE-Bench PRO 56.3 second place at release, Terminal-Bench 2.1 59.5) — directional, within the ~55–65 band.

**Sources**

- https://platform.stepfun.ai/docs/en/guides/models/step-3.7-flash (official: 198B/11B MoE, 256K context, image+video, tool calling, reasoning effort, pricing)
- https://github.com/stepfun-ai/Step-3.7-Flash (official weights/code repo)
- https://huggingface.co/stepfun-ai/Step-3.7-Flash (official weights)
- https://api.kilo.ai/api/gateway/models (live catalog, :free row verified 2026-09-05)
- https://kenari.id/v1/models (live catalog, :free row with "free": true verified 2026-09-05)
