---
name: Xinliu (iFlow / 心流)
url: "https://iflow.cn"
api_base: "https://apis.iflow.cn/v1"
setup_instructions: |
  1. Visit https://iflow.cn and complete registration/login.
  2. Open user settings and click the "个人信息" (profile) menu to generate your personal API KEY (manage it at https://iflow.cn/?open=setting).
  3. Call https://apis.iflow.cn/v1/chat/completions with header `Authorization: Bearer YOUR_API_KEY` using any OpenAI-compatible client, with a model ID from the support table.
api_key_url: "https://iflow.cn/?open=setting"
limits: {}
---

Xinliu (心流, "iFlow") is a CN AI-assistant product whose open docs (docs.iflow.cn) expose an OpenAI-compatible LLM chat API at apis.iflow.cn (quickstart verified live 2026-09-05).

**Free Tier:**

- Current documented state is free use: the official rate-limit page states the service is currently free ("当前服务免费使用") with a 1-concurrent-request limit — no price list, credit pack, or payment step appears anywhere in the LLM API docs. The "当前" (currently) wording means this can change; it is neither a stated permanent tier nor a quantified one-time grant.
- Account required; API key required (Bearer). No payment/billing step documented for the LLM API.

**Free Models:**

- `TBStars2-200B-A13B` — 32K context, 32K max output.
- `DeepSeek-R1` — 128K context, 32K max output.
- `DeepSeek-V3` — 128K context, 32K max output.
- [`Qwen3-32B`](../models/qwen3-32b.md) — 128K context, 32K max output.
- `Qwen3-235B` — 128K context, 32K max output.
- `Qwen3-Coder` — 256K context, 64K max output, code-optimized (full name Qwen3-Coder-480B-A35B; documented tool support: Claude Code, Cline, Roo Code).
- `KIMI-K2` — 128K context, 64K max output.
- `Qwen3-235B-A22B-Thinking-2507` — 256K context, 64K max output.
- `Qwen3-235B-A22B-Instruct` — 256K context, 64K max output.
- Model table verified live against the official quickstart 2026-09-05. Docs carry no per-model price split, so all listed models are treated as covered by the current free-use statement; the docs warn the roster may change (models added/removed) — verify live. None of these IDs currently has a model card in `models/`, so no card links apply.

**Limits:**

- 1 concurrent request per user; excess returns 429 (documented). Streaming requests release the slot immediately on cancel; non-streaming requests hold it until the model finishes.
- No documented per-minute, per-day, or token quotas (frontmatter `limits` therefore stays empty; concurrency is not a per-time rate).

**Notes:**

- Phone verification: unknown. Real-name verification: unknown. CN phone requirement: unknown.
- Separate offering: 心流·搜索 (platform.iflow.cn) is a credits-based web-search/image-search/fetch API for agents, not LLM inference, with paid credit packs — out of scope for this file. Note docs.iflow.cn root currently serves the search-platform front page; the LLM API quickstart remains live under the localized docs path (verified 2026-09-05).
- Base URL `https://apis.iflow.cn/v1/chat/completions` is documented as 100% OpenAI-compatible.
- Operator identity beyond the 心流/iFlow brand (contact service@iflow.cn) is undocumented in the API docs.
- Data usage/training policy: unknown.

**Sources**

- https://docs.iflow.cn/zh-Hant/docs/ (quickstart: model table, key steps, base URL verified 2026-09-05)
- https://docs.iflow.cn/zh-Hant/docs/api-reference/ (endpoint, Bearer auth, model param verified 2026-09-05)
- https://docs.iflow.cn/zh-Hant/docs/limitSpeed (currently-free statement, concurrency-1 limit)
- https://iflow.cn/ (official site, 心流AI助手)
- https://platform.iflow.cn/docs/credits (search-API credit pricing — separate product, for distinction only)
