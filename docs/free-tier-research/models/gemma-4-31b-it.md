---
name: Gemma 4 31B IT
developer: Google
canonical_id: google/gemma-4-31b-it
family: gemma
context_window: 262144
max_output_tokens: 32768
reasoning: true
tool_call: true
structured_output: true
temperature: true
modalities:
  input: [text, image]
  output: [text]
open_weights: true
providers:
  - name: UnoRouter
    file: unorouter
    model_id: gemma-4-31b-it:free
    conditions: ":free lane; account + key, no card"
    limits:
      requests:
        minute: 1
    verified: "2026-09-05"
  - name: Requesty
    file: requesty
    model_id: google/gemma-4-31b-it
    conditions: "Free-models tier ('free for now'); account + key, no card; quota shared across all free models combined"
    limits:
      requests:
        minute: 20
        day: 200
    verified: "2026-09-05"
---

Gemma 4 31B IT is Google's largest open Gemma instruction model, with image input alongside text (fixture-reported facts; verify live).

**Capabilities:**

- Reasoning, tool/function calling, structured output, temperature control (fixture-reported).
- Text + image in / text out; ~262K context (fixture-reported).
- Open weights.

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [UnoRouter](../providers/unorouter.md) | `gemma-4-31b-it:free` | `:free` lane; account + key, no card | ~1 req/min per user + upstream caps | 2026-09-05 |
| [Requesty](../providers/requesty.md) | `google/gemma-4-31b-it` | Free-models tier ("free for now"); account + key, no card | New orgs: 200 req/day + 20 req/min shared across all free models combined | 2026-09-05 |

**Notes:**

- Fixture-observed (re-verification lead, not in table): a `gemma-4-31b-it:free` row on Kenari and a $0 row on Nvidia NIM — confirm live via `GET /v1/models` / build.nvidia.com before use.

**Sources**

- raw/opencode-models-api/google/model_gemma-4-31b-it.json (capabilities/context — discovery data)
- https://unorouter.com/en/models
- https://docs.requesty.ai/features/free-models
