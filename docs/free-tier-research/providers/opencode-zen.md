---
name: OpenCode Zen
url: "https://opencode.ai"
setup_instructions: |
  1. No sign-up, no API key needed for the free models.
  2. Point any OpenAI-compatible client at base URL `https://opencode.ai/zen/v1` with no `Authorization` header (any placeholder value is likewise ignored).
  3. Call `POST /v1/chat/completions` with a `-free` model ID, or `POST /v1/responses` for `muse-spark-1.3-contributor-free`.
  4. For the paid catalog models on the same endpoint, a Zen account with billing details and `OPENCODE_API_KEY` is required instead.
api_key_url: "https://opencode.ai/auth"
default_api_key: public
limits: {}
---

OpenCode Zen is the AI gateway of the opencode harness. Alongside its billed catalog it serves 6 models at $0 input/output with no account and no API key; verified live 2026-09-05 (anonymous `POST /v1/chat/completions` returned real inference for 3 of them, the other 2 returned a free-pool rate limit, never a 401).

**Free Tier:**

- 6 models priced Free/Free/Free per 1M tokens, explicitly "for a limited time" (feedback-collection period per model team).
- Anonymous access; no sign-up, no key, no payment. The billed flow in the Zen docs (sign in + billing details + `OPENCODE_API_KEY`) applies to the paid catalog, not the free models.
- Free pool is rate-limited: over-capacity returns `FreeUsageLimitError` ("Rate limit exceeded. Please try again later."). Numerical limits are unpublished.

**Free Models:**

- `big-pickle` — stealth model, free for a limited time (pool exhausted at verification time).
- `mimo-v2.5-free` — Xiaomi MiMo, `/v1/chat/completions` (pool exhausted at verification time).
- `ling-3.0-flash-fin-free` — Inclusion AI finance-tuned, `/v1/chat/completions` (verified working anonymously).
- `nemotron-3-ultra-free` — NVIDIA Nemotron 3 Ultra 550B, `/v1/chat/completions` (verified working anonymously; 1M context per models.dev).
- `nemotron-3.5-lightning-free` — NVIDIA Nemotron 3.5 Lightning, `/v1/chat/completions` (verified working anonymously).
- `muse-spark-1.3-contributor-free` — Meta Muse Spark, served ONLY on `/v1/responses` (not `/v1/chat/completions`); in opencode config used as `opencode/muse-spark-1.3-contributor-free`.

**Limits:**

- No published RPM/RPD/TPM figures. Anonymous free pool enforced per observed `FreeUsageLimitError`; exact quota and reset window unknown.
- Full model roster and metadata: `GET https://opencode.ai/zen/v1/models` (no auth; returns the live catalog). Roster rotates without notice.

**Notes:**

- Limited-time offering per model; any of the 6 can revert to paid or be removed (a deprecation table is maintained in the Zen docs).
- Data usage while free: Big Pickle, MiMo-V2.5 Free and Ling 3.0 Flash Fin Free may use collected data to improve the model. Nemotron free endpoints are NVIDIA trial-use only (no personal/confidential data; use logged per NVIDIA API Trial Terms). Muse Spark Contributor Free exchanges heavily discounted pricing for permission to train future Meta models on prompts/completions.
- Opencode's console code geo-gates the contributor models by request country (`packages/console/app/src/lib/request-country.ts`) — availability may vary by region.
- Third-party router projects (codex-router, OmniRoute) independently classify `muse-spark-*-contributor-free` as anonymous/no-key models, consistent with the live verification.
- Do not confuse with the paid Zen catalog (GPT/Claude/Gemini/Grok/Qwen/DeepSeek/Kimi/GLM/MiniMax rows in the same pricing table), which requires a billed account.

**Sources**

- https://raw.githubusercontent.com/anomalyco/opencode/refs/heads/dev/packages/web/src/content/docs/zen.mdx (pricing + free-model statements + privacy exceptions)
- https://opencode.ai/zen/v1/models (live catalog, no auth)
- Live verification 2026-09-05: keyless `POST /zen/v1/chat/completions` (this session, from-research-host IP)
- https://github.com/anomalyco/opencode/blob/dev/packages/console/app/src/lib/request-country.ts (contributor-model geo-gating)
- https://github.com/anomalyco/opencode/blob/dev/packages/opencode/test/tool/fixtures/models-api.json (`opencode` provider entry: `OPENCODE_API_KEY`, `https://opencode.ai/zen/v1`)
