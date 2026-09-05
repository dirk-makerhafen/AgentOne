---
name: Nemotron 3.5 Content Safety
developer: Nvidia
canonical_id: nvidia/nemotron-3.5-content-safety
family: nemotron
context_window: 131072
reasoning: true
tool_call: false
temperature: true
modalities:
  input: [text, image]
  output: [text]
open_weights: true
providers:
  - name: Kilo Code
    file: kilo-code
    model_id: nvidia/nemotron-3.5-content-safety:free
    conditions: "Standing `:free` lane; anonymous keyless access allowed, no account/key/card; roster rotates"
    verified: "2026-09-05"
  - name: OpenRouter
    file: openrouter
    model_id: nvidia/nemotron-3.5-content-safety:free
    conditions: "Permanent `:free` variant; account + key, no card; free-model caps apply account-wide; roster rotates"
    verified: "2026-09-05"
  - name: Requesty
    file: requesty
    model_id: nvidia/nemotron-3.5-content-safety
    conditions: "Free-models tier ('free for now'); account + key, no card; quota shared across all free models combined"
    limits:
      requests:
        minute: 20
        day: 200
    verified: "2026-09-05"
---

**Guardrail model — not a general chat model.** Nemotron 3.5 Content Safety is Nvidia's customizable multimodal safety classifier: a fine-tuned Google Gemma-3-4B-it (4B params, LoRA, decoder-only Transformer + SigLIP vision encoder) that labels prompts and model responses safe/unsafe against the Aegis V2 taxonomy, with optional custom-policy reasoning. Use it as a moderation judge inside agent pipelines, not as a conversational model.

**Capabilities:**

- Safety classification of user prompts (plus an optional image) and assistant responses: `User Safety` / `Response Safety` safe-or-unsafe labels plus violated safety categories (official model card).
- Custom-policy mode: bring-your-own safety definitions with a concise reasoning trace (`enable_thinking=True/False` chat-template flag) before the final classification (official model card).
- Multimodal input (text + single image, 896x896) and multilingual coverage (English, Arabic, German, Spanish, French, Hindi, Japanese, Thai, Dutch, Italian, Korean, Chinese) (official model card).
- Text in (+ optional image) / text-label out; context up to 128K (official model card).
- No general tool/function calling: it is a classifier, not an agent model.
- Open weights on Hugging Face under OpenMDW-1.1 (plus the Gemma Terms of Use and Gemma Prohibited Use Policy, which also govern use).

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Kilo Code](../providers/kilo-code.md) | `nvidia/nemotron-3.5-content-safety:free` | Standing `:free` lane; anonymous keyless access allowed, no account/key/card | None published combo-specific; provider-wide anonymous `:free` quota applies (see provider file); roster rotates | 2026-09-05 |
| [OpenRouter](../providers/openrouter.md) | `nvidia/nemotron-3.5-content-safety:free` | Permanent `:free` variant; account + key, no card | None published combo-specific; provider-wide free-model caps apply (see provider file); roster rotates | 2026-09-05 |
| [Requesty](../providers/requesty.md) | `nvidia/nemotron-3.5-content-safety` | Free-models tier ("free for now"); account + key, no card | New orgs: 200 req/day + 20 req/min shared across all free models combined | 2026-09-05 |

**Notes:**

- Catalog fit: included because it is genuinely usable free LLM API inference (chat-completions-compatible classifier, free on three verified providers), but flagged here and in the intro as a guardrail — do not evaluate it against chat-model benchmarks.
- `reasoning: true` reflects only the optional custom-policy reasoning trace, not general chain-of-thought problem solving.
- `tool_call: false` — no function-calling interface is documented; it returns safety labels, not tool calls.
- `max_output_tokens`: no official figure found — omitted.
- Knowledge cutoff: no official date found — omitted.
- License nuance: unlike the chat Nemotron models (OpenMDW-1.1 only), this model is additionally governed by the Gemma Terms of Use and Gemma Prohibited Use Policy (official model card) because of its Gemma-3-4B-it base.
- Release: Hugging Face 2026-06-02 (model card v1.2); Build.NVIDIA.com listing 2026-06-02.

**Sources**

- https://huggingface.co/nvidia/Nemotron-3.5-Content-Safety (official: Gemma-3-4B-it base, 4B LoRA, 128K context, text+image in / label out, reasoning flag, Aegis V2 taxonomy, OpenMDW-1.1 + Gemma terms, release date)
- https://build.nvidia.com/nvidia/nemotron-3.5-content-safety/modelcard (official model card mirror)
- https://huggingface.co/blog/nvidia/nemotron-3-5-content-safety (official announcement: multilingual/multimodal accuracy)
- ../providers/kilo-code.md (`nvidia/nemotron-3.5-content-safety:free`, 128K context — live catalog 2026-09-05)
- ../providers/openrouter.md (`nvidia/nemotron-3.5-content-safety:free` — live roster 2026-09-05)
- ../providers/requesty.md (`nvidia/nemotron-3.5-content-safety` free input/output — free-models doc 2026-09-05)
