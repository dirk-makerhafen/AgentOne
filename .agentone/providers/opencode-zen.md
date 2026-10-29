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

OpenCode Zen is the AI gateway of the opencode harness. Alongside its billed catalog it serves free models at $0 input/output with no account and no API key; re-verified live 2026-09-05 (anonymous calls returned real inference for `ling-3.0-flash-fin-free` and both Muse Spark contributor models; `big-pickle` and `mimo-v2.5-free` returned free-pool rate limits, never a 401). Updated with 31 free models from opencode fixtures (2026-10-28).

**Free Tier:**

- Models priced Free/Free/Free per 1M tokens, explicitly "for a limited time" (feedback-collection period per model team).
- Anonymous access; no sign-up, no key, no payment. The billed flow in the Zen docs (sign in + billing details + `OPENCODE_API_KEY`) applies to the paid catalog, not the free models.
- Free pool is rate-limited: over-capacity returns `FreeUsageLimitError` ("Rate limit exceeded. Please try again later."). Numerical limits are unpublished.

**Free Models (verified 2026-10-28 from opencode fixtures + live API):**

### Reflection AI Family
- `beam-free` — 1M context, 131K max output, reasoning (effort), tool calls, open weights (2026-10-05)

### Recursive AI Family
- `flint-40b-free` — 262K context, 65K max output, reasoning (effort), tool calls, open weights (2026-10-21)

### Xiaomi MiMo Family
- `mimo-v2.5-free` — 200K context, reasoning, tool calls, open weights
- `mimo-v2-omni-free` — 262K context, reasoning, tool calls, open weights
- `mimo-v2-flash-free` — 262K context, reasoning, tool calls, open weights
- `mimo-v2-pro-free` — 1M context, reasoning, tool calls, open weights
- `mimo-v2.6-flash-free` — 200K context, 32K max output, reasoning, tool calls, multimodal (text/image/audio/video), open weights (2026-09-22)

### NVIDIA Nemotron Family
- `nemotron-3-ultra-free` — 1M context, 128K max output, reasoning, tool calls, open weights (2026-06-04)
- `nemotron-3-super-free` — 1M context, 66K max output, reasoning, tool calls, open weights (2026-03-11)
- `nemotron-3.5-super-vl-free` — 1M context (1M input / 131K output), reasoning (effort), tool calls, vision (text/image), open weights (2026-10-15)
- `nemotron-3.5-lightning-free` — 1M context, reasoning, tool calls, open weights (2026-08-11)

### DeepSeek Family
- `deepseek-v4-flash-free` — 200K context, 128K max output, reasoning, tool calls, open weights (2026-04-24)
- `deepseek-v4.1-flash-free` — 200K context, 32K max output, reasoning (toggle+effort), tool calls, vision (text/image), open weights (2026-09-10)

### Qwen Family
- `qwen3.6-plus-free` — 1M context, reasoning, tool calls, open weights

### Kimi (Moonshot) Family
- `kimi-k2.5-free` — 262K context, reasoning, tool calls, open weights

### GLM (Z.ai) Family
- `glm-5-free` — 205K context, reasoning, tool calls, open weights (2026-02-11)
- `glm-4.7-free` — 205K context, reasoning, tool calls, open weights (2025-12-22)
- `glm-5.3-flash-free` — 200K context, 32K max output, reasoning (effort), tool calls, multimodal (text/image/video), open weights (2026-08-26)

### TypeSafe Family
- `jev-1.13-free` — 262K context, 65K max output, reasoning (effort), tool calls, System One interface (structured decisions with calibrated confidence), proprietary (2026-10-20)

### Other Free Models
- `big-pickle` — 200K context, reasoning, tool calls, open weights (stealth model)
- `grok-code` — 256K context, reasoning, tool calls (xAI)
- `ring-2.6-1t-free` — 262K context, reasoning, tool calls, open weights
- `north-mini-code-free` — 256K context, reasoning, tool calls (Cohere, code-specialized)
- `trinity-large-preview-free` — 131K context, tool calls
- `ling-2.6-flash-free` — 262K context, tool calls (Inclusion AI)
- `hy3-free` — 190K context, reasoning, tool calls, open weights (Hunyuan)
- `hy3-preview-free` — 256K context, reasoning, tool calls, open weights (Hunyuan)
- `gpt-5-nano` — 400K context, reasoning, tool calls, open weights (OpenAI)

**Previously Verified Free Models (2026-09-05, may still be available):**
- `ling-3.0-flash-fin-free` — Inclusion AI finance-tuned, `/v1/chat/completions`
- `muse-spark-1.3-contributor-free` — Meta Muse Spark, served ONLY on `/v1/responses`
- `muse-spark-1.2-contributor-free` — Meta Muse Spark 1.2, served on `/v1/responses` (NOT in published pricing table)

**Limits:**

- No published RPM/RPD/TPM figures. Anonymous free pool enforced per observed `FreeUsageLimitError`; exact quota and reset window unknown.
- Full model roster and metadata: `GET https://opencode.ai/zen/v1/models` (no auth; 80+ models on 2026-10-28). Roster rotates without notice.

**Notes:**

- Limited-time offering per model; any free model can revert to paid or be removed (a deprecation table is maintained in the Zen docs).
- `deepseek-v4-flash-free` appears in the live `/v1/models` catalog but returned "Model is unavailable" (upstream) on anonymous test 2026-09-05 — not currently usable, not listed as a free model.
- Data usage while free: Big Pickle, MiMo-V2.5 Free and Ling 3.0 Flash Fin Free may use collected data to improve the model. Nemotron free endpoints are NVIDIA trial-use only (no personal/confidential data; use logged per NVIDIA API Trial Terms). Muse Spark Contributor Free exchanges heavily discounted pricing for permission to train future Meta models on prompts/completions.
- Opencode's console code geo-gates the contributor models by request country (`packages/console/app/src/lib/request-country.ts`) — availability may vary by region.
- Third-party router projects (codex-router, OmniRoute) independently classify `muse-spark-*-contributor-free` as anonymous/no-key models, consistent with the live verification.
- Do not confuse with the paid Zen catalog (GPT/Claude/Gemini/Grok/Qwen/DeepSeek/Kimi/GLM/MiniMax rows in the same pricing table), which requires a billed account.

**Sources**

- https://raw.githubusercontent.com/anomalyco/opencode/refs/heads/dev/packages/web/src/content/docs/zen.mdx (pricing + free-model statements + privacy exceptions; re-checked 2026-09-05 — same 6 Free rows)
- https://opencode.ai/zen/v1/models (live catalog, no auth — 80+ models checked 2026-10-28)
- Live verification 2026-09-05: keyless `POST /zen/v1/chat/completions` and `POST /zen/v1/responses` (this session, from-research-host IP)
- https://github.com/anomalyco/opencode/blob/dev/packages/console/app/src/lib/request-country.ts (contributor-model geo-gating)
- https://github.com/anomalyco/opencode/blob/dev/packages/opencode/test/tool/fixtures/models-api.json (`opencode` provider entry: `OPENCODE_API_KEY`, `https://opencode.ai/zen/v1`)
- docs/free-tier-research/raw/opencode-models-api/opencode/ (87 model fixtures, 31 free models, verified 2026-10-28)