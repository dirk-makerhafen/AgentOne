---
name: Xinliu (iFlow / 心流)
url: https://iflow.cn
api_base: https://apis.iflow.cn/v1
setup_instructions: '1. Visit https://iflow.cn and complete registration/login.

  2. Open user settings and click the "个人信息" (profile) menu to generate your personal
  API KEY (manage it at https://iflow.cn/?open=setting).

  3. Call https://apis.iflow.cn/v1/chat/completions with header `Authorization: Bearer
  YOUR_API_KEY` using any OpenAI-compatible client, with a model ID from the support
  table.

  '
api_key_url: https://iflow.cn/?open=setting
---

Xinliu (心流, "iFlow") is a CN AI-assistant product whose open docs (docs.iflow.cn) expose an OpenAI-compatible LLM chat API at apis.iflow.cn (quickstart verified live 2026-09-05).

**Sources**

- https://docs.iflow.cn/zh-Hant/docs/ (quickstart: model table, key steps, base URL verified 2026-09-05)
- https://docs.iflow.cn/zh-Hant/docs/api-reference/ (endpoint, Bearer auth, model param verified 2026-09-05)
- https://docs.iflow.cn/zh-Hant/docs/limitSpeed (currently-free statement, concurrency-1 limit)
- https://iflow.cn/ (official site, 心流AI助手)
- https://platform.iflow.cn/docs/credits (search-API credit pricing — separate product, for distinction only)
