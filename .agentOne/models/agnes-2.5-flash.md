---
name: Agnes 2.5 Flash
developer: Agnes AI
canonical_id: agnes-ai/agnes-2.5-flash
leaderboard_rank_estimated: "~60"
family: agnes-flash
context_window: 524288
reasoning: true
tool_call: true
modalities:
  input: [text, image]
  output: [text]
open_weights: true
providers:
  - name: Agnes AI
    file: agnes-ai
    model_id: agnes-2.5-flash
    conditions: "Core models free indefinitely per platform FAQ; account + key"
    verified: "2026-09-05"
  - name: Kenari
    file: kenari
    model_id: agnes-2-5-flash:free
    conditions: ":free lane billed Rp 0, best-effort; account + key (kn-...), no top-up"
    verified: "2026-09-05"
  - name: ZenMux
    file: zenmux
    model_id: sapiens-ai/agnes-2.5-flash
    conditions: "Free lane billed $0/token (in, out); account + key, no card; rate-limited; roster rotates"
    verified: "2026-09-06"
---

Agnes 2.5 Flash is Agnes AI's generally-available fast coding/agent text model, with improved coding, agent workflows, tool calling, and image understanding over the deprecated Agnes 2.0 Flash (official model docs). No official SWE-bench score is published; internal/company-reported figures (~75.6 SWE-bench Verified, ~62.3 Terminal-Bench 2.1) suggest frontier-adjacent coding, so the leaderboard rank is an estimate (see Notes).

**Capabilities:**

- Code-specialized: generation, debugging, refactoring, explanation, and patch-style agentic coding workflows (official docs).
- Tool calling (`tools` / `tool_choice`), multi-turn conversations, streaming, and optional Thinking mode for coding/reasoning/agent work (official docs).
- Image understanding via public image URLs alongside text input; text and image input with text output (official docs).
- Chat Completions, Responses, and Anthropic-compatible Messages APIs on the same model name (official docs).
- Base weights open (Agnes-AI/Agnes-2.5-Flash-Base: 202B-param sparse MoE on Hugging Face, Apache 2.0).

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Agnes AI](../providers/agnes-ai.md) | `agnes-2.5-flash` | Core models free indefinitely per platform FAQ; account + key | Text-model RPM for free/default users per provider file (no combo-specific cap) | 2026-09-05 |
| [Kenari](../providers/kenari.md) | `agnes-2-5-flash:free` | `:free` lane billed Rp 0, best-effort; account + key (`kn-...`), no top-up | Per-minute cap plus tiered daily quotas, operator-set (see provider file) | 2026-09-05 |
| [ZenMux](../providers/zenmux.md) | `sapiens-ai/agnes-2.5-flash` | Free lane billed $0/token (in, out); account + key, no card | Served at 524K context; rate-limited; exact limits unpublished; roster rotates | 2026-09-06 |

**Notes:**

- Same-model $0 coverage: `agnes-2.5-flash` is $0 on Agnes AI itself, `:free` on Kenari, and on ZenMux's free lane as `sapiens-ai/agnes-2.5-flash`.
- Kenari's non-suffixed `agnes-2-5-flash` is metered per that file's own notes — only the `:free`-suffixed ID is claimed here.
- Context: official Agnes docs state `512K` for 2.5-flash (card default 524288); Kenari catalogs 512K for `agnes-2-5-flash:free`. No per-provider override recorded.
- `max_output_tokens`: official docs state `65.5K` (not an exact integer) — omitted rather than converted.
- Deprecated sibling Agnes 2.0 Flash is intentionally not catalogued (superseded ≥1yr-old generation; see README "Filenames" rule) — it remains `:free` on Kenari/UnoRouter only as a legacy row there.
- Agnes 2.5 Pro (flagship, previewed July 2026) is billed, not free — not claimed.
- `leaderboard_rank_estimated: "~60"` (2026-09-05): no `leaderboard.csv` entry (absent from the 2026-09-06 CSV refresh); internal/company-reported figures (~75.6 SWE-bench Verified, ~62.3 Terminal-Bench 2.1) place it near the hy3/step-3-flash cluster (rank ~51–67) — directional, unverified externally.

**Sources**

- https://wiki.agnes-ai.com/en/docs/agnes-25-flash (official: GA upgrade, tool calling, image URL input, Thinking mode, 512K context, 65.5K max output, $0 current price)
- https://wiki.agnes-ai.com/en/docs/pricing (official: $0 prices, 2.0-flash deprecation, verified via provider file 2026-09-05)
- https://wiki.agnes-ai.com/en/docs/faqs (official: indefinite free use, verified via provider file 2026-09-05)
- https://huggingface.co/Agnes-AI/Agnes-2.5-Flash-Base (official base weights, Apache 2.0, 202B MoE)
- https://kenari.id/v1/models (live catalog, `agnes-2-5-flash:free` row verified 2026-09-05)
- Third-party benchmark coverage of 2.5-flash (internal claims, directional only — basis for the estimated rank) — re-verify externally before relying on the ~60 figure.