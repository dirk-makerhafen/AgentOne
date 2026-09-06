---
name: Kilo Code
url: "https://kilo.ai"
default_api_key: public
setup_instructions: |
  1. No signup needed for anonymous free access — call the gateway directly (rate-limited per IP).
  2. Optional: sign in at https://app.kilo.ai to obtain a JWT API key (tied to your Kilo account) for keyed use and paid models.
  3. Point any OpenAI-compatible client at https://api.kilo.ai/api/gateway with `model` set to `kilo-auto/free` or a `:free` model ID.
  4. Send `Authorization: Bearer $KILO_API_KEY` when using a key; omit it for anonymous `:free` calls.
api_key_url: "https://app.kilo.ai"
limits:
  requests:
    hour: 200
---

Kilo Code's Kilo Gateway is a unified OpenAI-compatible API over 500+ models with a standing free tier, including keyless anonymous access to models tagged `:free`.

**Free Tier:**

- Free models at $0 prompt/completion — not trial credits.
- `kilo-auto/free` router resolves each session to a curated free model with no credits required.
- Anonymous (no key, IP-identified) access permitted for `:free` models only: 200 requests/hour per IP (official auth docs, verified 2026-09-05).

**Free Models:**

Live catalog (`GET https://api.kilo.ai/api/gateway/models`, no auth) returned 371 models on 2026-09-05; the rows below had $0 prompt AND $0 completion pricing. Roster rotates server-side without notice — verify live before use.

- `kilo-auto/free` — dynamic free-model router, no credits required (context 256K per catalog).
- [`stepfun/step-3.7-flash:free`](../models/step-3-7-flash.md) — 262K context, text + vision.
- [`poolside/laguna-s-2.1:free`](../models/laguna-s-2.1.md) — 262144 context, code-specialized.
- [`poolside/laguna-xs-2.1:free`](../models/laguna-xs-2.1.md) — 262144 context, code-specialized.
- [`minimax/minimax-m3:free`](../models/minimax-m3.md) — 1048576 context (newer row, confirmed live 2026-09-05).
- [`minimax/minimax-m2.7:free`](../models/minimax-m2.7.md) — 196608 context.
- [`nvidia/nemotron-3-ultra-550b-a55b:free`](../models/nemotron-3-ultra-550b-a55b.md) — 1M context.
- [`nvidia/nemotron-3-super-120b-a12b:free`](../models/nemotron-3-super-120b-a12b.md) — 262144 context.
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` — 256K context, multimodal reasoning.
- [`nvidia/nemotron-3.5-lightning:free`](../models/nemotron-3.5-lightning.md) — 1M context.
- `nvidia/nemotron-3.5-content-safety:free` — 128K context (4B guardrail classifier, not a chat model; small specialist, deliberately not catalogued as a model card).
- [`inclusionai/ling-3.0-flash-fin:free`](../models/ling-3.0-flash-fin.md) — 262144 context.
- [`inclusionai/ling-3.0-flash-sante:free`](../models/ling-3.0-flash-sante.md) — 262144 context.
- [`cohere/north-mini-code:free`](../models/north-mini-code.md) — 256K context, code-specialized.
- [`thinkingmachines/inkling:free`](../models/inkling.md) — 1048576 context.
- [`thinkingmachines/inkling-small:free`](../models/inkling-small.md) — 1048576 context.
- [`dots-studio/dots-3-note-preview:free`](../models/dots-3-note.md) — 512000 context.
- [`liquid/lfm-2.5-2.6b:free`](../models/lfm-2.5.md) — 64K context.
- `openrouter/free` — best-available-free-model alias (context varies).
- Full current list (no auth): `GET https://api.kilo.ai/api/gateway/models`.

**Limits:**

- Anonymous `:free` access: 200 requests/hour per IP (official docs).
- Authenticated free-model limits: unknown — not published.

**Notes:**

- No account, key, payment, or phone required for anonymous `:free` calls; key required for paid models.
- `tencent/hy3:free` (previously listed) was absent from the live catalog on 2026-09-05 — roster rotates; do not rely on removed IDs.
- Data handling: Auto Free may route to providers that log prompts/outputs for service improvement; NVIDIA free endpoints are trial-use only with session logging under NVIDIA API Trial Terms — do not submit personal or confidential data on free routes.
- Free-model roster and `kilo-auto` routing change server-side without notice.
- No credit card required.

**Sources**

- https://kilo.ai/docs/gateway/authentication (anonymous `:free` access, 200 req/hr/IP, JWT keys)
- https://kilo.ai/docs/getting-started/using-kilo-for-free (Auto Free router, data-handling warning)
- https://api.kilo.ai/api/gateway/models (live catalog, no auth — 371 models, `:free` rows verified 2026-09-05)
- https://kilo.ai/docs/gateway/models-and-providers
- https://kilo.ai/docs/gateway/api-reference
- http://kilo.ai/gateway
- https://freellms.org/providers/kilo-code/
- https://github.com/nejib1/Free-LLM
