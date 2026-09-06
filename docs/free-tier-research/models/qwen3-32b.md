---
name: Qwen3-32B
developer: Alibaba (Qwen team)
canonical_id: qwen/qwen3-32b
leaderboard_id: qwen3-32b
leaderboard_rank: 163
family: qwen3
context_window: 32768
max_output_tokens: 32768
reasoning: true
tool_call: true
temperature: true
modalities:
  input: [text]
  output: [text]
open_weights: true
providers:
  - name: OVHcloud AI Endpoints
    file: ovhcloud-ai-endpoints
    model_id: Qwen3-32B
    conditions: "Anonymous tier; no account, key, or card; throttled per IP"
    limits:
      requests:
        minute: 2
    verified: "2026-09-05"
  - name: Xinliu (iFlow / 心流)
    file: xinliu
    model_id: Qwen3-32B
    conditions: "Currently free per rate-limit page; account + key; roster may change"
    verified: "2026-09-05"
---

Qwen3-32B is Alibaba Qwen team's 32.8B dense reasoning model (thinking/non-thinking modes, Apache 2.0 open weights): 32,768 tokens native context, validated to 131,072 via YaRN.

**Capabilities:**

- Reasoning (thinking mode on by default, hard `/think`+`/no_think` switches), tool/function calling via Qwen-Agent, temperature control (official model card).
- Text in / text out; 32,768 native context (131,072 with YaRN); 32,768 recommended output length.
- Open weights (Hugging Face `Qwen/Qwen3-32B`, FP8/AWQ/GGUF variants).

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [OVHcloud AI Endpoints](../providers/ovhcloud-ai-endpoints.md) | `Qwen3-32B` | Anonymous tier; no account, key, or card | 2 req/min per IP per model; roster rotates | 2026-09-05 |
| [Xinliu (iFlow / 心流)](../providers/xinliu.md) | `Qwen3-32B` | Currently free per rate-limit page; account + key | 1 concurrent request per user (provider-wide); Xinliu docs report 128K context / 32K max output for its deployment | 2026-09-05 |

**Notes:**

- Xinliu's "currently free" wording is neither a stated permanent tier nor a quantified grant — it can change; re-verify the rate-limit page.
- OVHcloud keyed access requires a payment method and is billed per token — only the anonymous lane is free.

**Sources**

- https://huggingface.co/Qwen/Qwen3-32B (32,768 native / 131,072 YaRN, tool calling, thinking modes, 32768 output)
- https://docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/ai-endpoints-capabilities (anonymous 2 RPM)
- https://docs.iflow.cn/zh-Hant/docs/ (model table, key steps, base URL)
- https://docs.iflow.cn/zh-Hant/docs/limitSpeed (currently-free statement, concurrency-1 limit)
