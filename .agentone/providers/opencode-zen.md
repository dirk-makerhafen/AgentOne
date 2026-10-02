---
name: OpenCode Zen
url: "https://opencode.ai"
api_base: "https://opencode.ai/zen/v1"
setup_instructions: |
  1. No sign-up, no API key needed for the free models.
  2. Point any OpenAI-compatible client at base URL `https://opencode.ai/zen/v1` with no `Authorization` header (any placeholder value is likewise ignored).
  3. Call `POST /v1/chat/completions` with a `-free` model ID, or `POST /v1/responses` for `muse-spark-1.3-contributor-free` and `muse-spark-1.2-contributor-free`.
  4. For the paid catalog models on the same endpoint, a Zen account with billing details and `OPENCODE_API_KEY` is required instead.
api_key_url: "https://opencode.ai/auth"
default_api_key: public
limits: {}
---

OpenCode Zen is the AI gateway of the opencode harness. Alongside its billed catalog it serves free models at $0 input/output with no account and no API key; re-verified live 2026-09-05 (anonymous calls returned real inference for `ling-3.0-flash-fin-free` and both Muse Spark contributor models; `big-pickle` and `mimo-v2.5-free` returned free-pool rate limits, never a 401).

**Free Tier:**

- Models priced Free/Free/Free per 1M tokens, explicitly "for a limited time" (feedback-collection period per model team). 6 models carry this pricing in the Zen docs; a 7th (`muse-spark-1.2-contributor-free`) works anonymously but is absent from the published pricing table (see Notes).
- Anonymous access; no sign-up, no key, no payment. The billed flow in the Zen docs (sign in + billing details + `OPENCODE_API_KEY`) applies to the paid catalog, not the free models.
- Free pool is rate-limited: over-capacity returns `FreeUsageLimitError` ("Rate limit exceeded. Please try again later."). Numerical limits are unpublished.

**Free Models:**

- `big-pickle` — stealth model, free for a limited time. Still priced Free in the docs, but absent from the live `/v1/models` catalog on 2026-09-05; live test returned `FreeUsageLimitError` (route exists, pool exhausted).
- [`mimo-v2.5-free`](../models/mimo-v2.5.md) — Xiaomi MiMo, `/v1/chat/completions` (pool exhausted at verification time).
- [`ling-3.0-flash-fin-free`](../models/ling-3.0-flash-fin.md) — Inclusion AI finance-tuned, `/v1/chat/completions` (verified working anonymously 2026-09-05).
- [`nemotron-3-ultra-free`](../models/nemotron-3-ultra-550b-a55b.md) — NVIDIA Nemotron 3 Ultra 550B, `/v1/chat/completions` (verified working anonymously; 1M context per models.dev).
- [`nemotron-3.5-lightning-free`](../models/nemotron-3.5-lightning.md) — NVIDIA Nemotron 3.5 Lightning, `/v1/chat/completions` (verified working anonymously).
- [`muse-spark-1.3-contributor-free`](../models/muse-spark-1.3-contributor.md) — Meta Muse Spark, served ONLY on `/v1/responses` (not `/v1/chat/completions`); in opencode config used as `opencode/muse-spark-1.3-contributor-free` (verified working anonymously 2026-09-05).
- [`muse-spark-1.2-contributor-free`](../models/muse-spark-1.2-contributor.md) — Meta Muse Spark 1.2, served on `/v1/responses`; returned a completed anonymous response on 2026-09-05. NOT in the published pricing table — free status is live-observed only and may be revoked without notice.

**Limits:**

- No published RPM/RPD/TPM figures. Anonymous free pool enforced per observed `FreeUsageLimitError`; exact quota and reset window unknown.
- Full model roster and metadata: `GET https://opencode.ai/zen/v1/models` (no auth; 70 models on 2026-09-05). Roster rotates without notice.

**Notes:**

- Limited-time offering per model; any free model can revert to paid or be removed (a deprecation table is maintained in the Zen docs).
- `deepseek-v4-flash-free` appears in the live `/v1/models` catalog but returned "Model is unavailable" (upstream) on anonymous test 2026-09-05 — not currently usable, not listed as a free model.
- Data usage while free: Big Pickle, MiMo-V2.5 Free and Ling 3.0 Flash Fin Free may use collected data to improve the model. Nemotron free endpoints are NVIDIA trial-use only (no personal/confidential data; use logged per NVIDIA API Trial Terms). Muse Spark Contributor Free exchanges heavily discounted pricing for permission to train future Meta models on prompts/completions.
- Opencode's console code geo-gates the contributor models by request country (`packages/console/app/src/lib/request-country.ts`) — availability may vary by region.
- Third-party router projects (codex-router, OmniRoute) independently classify `muse-spark-*-contributor-free` as anonymous/no-key models, consistent with the live verification.
- Do not confuse with the paid Zen catalog (GPT/Claude/Gemini/Grok/Qwen/DeepSeek/Kimi/GLM/MiniMax rows in the same pricing table), which requires a billed account.

**Sources**

- https://raw.githubusercontent.com/anomalyco/opencode/refs/heads/dev/packages/web/src/content/docs/zen.mdx (pricing + free-model statements + privacy exceptions; re-checked 2026-09-05 — same 6 Free rows)
- https://opencode.ai/zen/v1/models (live catalog, no auth — 70 models checked 2026-09-05)
- Live verification 2026-09-05: keyless `POST /zen/v1/chat/completions` and `POST /zen/v1/responses` (this session, from-research-host IP)
- https://github.com/anomalyco/opencode/blob/dev/packages/console/app/src/lib/request-country.ts (contributor-model geo-gating)
- https://github.com/anomalyco/opencode/blob/dev/packages/opencode/test/tool/fixtures/models-api.json (`opencode` provider entry: `OPENCODE_API_KEY`, `https://opencode.ai/zen/v1`)
