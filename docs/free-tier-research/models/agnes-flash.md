---
name: Zhipu Agnes 2.x Flash (family)
developer: Agnes AI
canonical_id: agnes-ai/agnes-2.5-flash
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
    model_id:
      - agnes-2-5-flash:free
      - agnes-2-0-flash:free
    conditions: ":free lane billed Rp 0, best-effort; account + key (kn-...), no top-up"
    notes: "agnes-2.0-flash is deprecated upstream; migrate to 2.5-flash"
    verified: "2026-09-05"
  - name: UnoRouter
    file: unorouter
    model_id: agnes-2.0-flash:free
    conditions: ":free lane; account + key, no card"
    limits:
      requests:
        minute: 1
    verified: "2026-09-05"
---

Zhipu Agnes 2.x Flash is Agnes AI's family of fast coding/agent text models. Agnes 2.5 Flash is the generally available upgrade of the deprecated Agnes 2.0 Flash, with improved coding, agent workflows, tool calling, and image understanding (official model docs). Both generations have genuine $0 lanes on at least two providers each.

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
| [Kenari](../providers/kenari.md) | `agnes-2-5-flash:free`, `agnes-2-0-flash:free` | `:free` lane billed Rp 0, best-effort; account + key (`kn-...`), no top-up | Per-minute cap plus tiered daily quotas, operator-set (see provider file); 2.0-flash deprecated upstream | 2026-09-05 |
| [UnoRouter](../providers/unorouter.md) | `agnes-2.0-flash:free` | `:free` lane; account + key, no card | ~1 req/min per user + upstream caps | 2026-09-05 |

**Notes:**

- Same-model $0 coverage: 2.5-flash is $0 on Agnes AI itself and `:free` on Kenari; 2.0-flash is `:free` on both Kenari and UnoRouter despite its deprecated status.
- Kenari's non-suffixed IDs are metered per that file's own notes — only the `:free`-suffixed IDs are claimed here.
- Context: official Agnes docs state `512K` for 2.5-flash (card default 524288); Kenari catalogs ~256K for `agnes-2-0-flash:free` and 512K for `agnes-2-5-flash:free`. No per-provider override recorded since neither figure contradicts the 2.5-flash default for its own version.
- `max_output_tokens`: official docs state `65.5K` (not an exact integer) — omitted rather than converted.
- Agnes 2.5 Pro (flagship, previewed July 2026) is billed, not free — not claimed.

**Sources**

- https://wiki.agnes-ai.com/en/docs/agnes-25-flash (official: GA upgrade, tool calling, image URL input, Thinking mode, 512K context, 65.5K max output, $0 current price)
- https://wiki.agnes-ai.com/en/docs/pricing (official: $0 prices, 2.0-flash deprecation, verified via provider file 2026-09-05)
- https://wiki.agnes-ai.com/en/docs/faqs (official: indefinite free use, verified via provider file 2026-09-05)
- https://huggingface.co/Agnes-AI/Agnes-2.5-Flash-Base (official base weights, Apache 2.0, 202B MoE)
- https://kenari.id/v1/models (live catalog, both :free rows verified 2026-09-05)
- https://unorouter.com/en/models (live free catalog, 2.0-flash row verified 2026-09-05)
