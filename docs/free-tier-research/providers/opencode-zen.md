---
name: OpenCode Zen
url: https://opencode.ai
api_base: https://opencode.ai/zen/v1
setup_instructions: '1. No sign-up, no API key needed for the free models.

  2. Point any OpenAI-compatible client at base URL `https://opencode.ai/zen/v1` with
  no `Authorization` header (any placeholder value is likewise ignored).

  3. Call `POST /v1/chat/completions` with a `-free` model ID, or `POST /v1/responses`
  for `muse-spark-1.3-contributor-free` and `muse-spark-1.2-contributor-free`.

  4. For the paid catalog models on the same endpoint, a Zen account with billing
  details and `OPENCODE_API_KEY` is required instead.

  '
api_key_url: https://opencode.ai/auth
default_api_key: public
---

OpenCode Zen is the AI gateway of the opencode harness. Alongside its billed catalog it serves free models at $0 input/output with no account and no API key; re-verified live 2026-09-05 (anonymous calls returned real inference for `ling-3.0-flash-fin-free` and both Muse Spark contributor models; `big-pickle` and `mimo-v2.5-free` returned free-pool rate limits, never a 401). Updated with 31 free models from opencode fixtures (2026-10-28).

**Sources**

- https://raw.githubusercontent.com/anomalyco/opencode/refs/heads/dev/packages/web/src/content/docs/zen.mdx (pricing + free-model statements + privacy exceptions; re-checked 2026-09-05 — same 6 Free rows)
- https://opencode.ai/zen/v1/models (live catalog, no auth — 80+ models checked 2026-10-28)
- Live verification 2026-09-05: keyless `POST /zen/v1/chat/completions` and `POST /zen/v1/responses` (this session, from-research-host IP)
- https://github.com/anomalyco/opencode/blob/dev/packages/console/app/src/lib/request-country.ts (contributor-model geo-gating)
- https://github.com/anomalyco/opencode/blob/dev/packages/opencode/test/tool/fixtures/models-api.json (`opencode` provider entry: `OPENCODE_API_KEY`, `https://opencode.ai/zen/v1`)
- docs/free-tier-research/raw/opencode-models-api/opencode/ (87 model fixtures, 31 free models, verified 2026-10-28)
