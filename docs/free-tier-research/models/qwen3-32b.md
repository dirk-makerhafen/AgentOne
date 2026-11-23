---
name: Qwen3-32B
developer: Alibaba (Qwen team)
canonical_id: qwen/qwen3-32b
leaderboard_id: qwen3-32b
leaderboard_rank: 155
family: qwen3
context_window: 32768
max_output_tokens: 32768
reasoning: true
tool_call: true
temperature: true
modalities:
  input:
  - text
  output:
  - text
open_weights: true
---

Qwen3-32B is Alibaba Qwen team's 32.8B dense reasoning model (thinking/non-thinking modes, Apache 2.0 open weights): 32,768 tokens native context, validated to 131,072 via YaRN.

**Capabilities:**

- Reasoning (thinking mode on by default, hard `/think`+`/no_think` switches), tool/function calling via Qwen-Agent, temperature control (official model card).
- Text in / text out; 32,768 native context (131,072 with YaRN); 32,768 recommended output length.
- Open weights (Hugging Face `Qwen/Qwen3-32B`, FP8/AWQ/GGUF variants).

**Notes:**

- Xinliu's "currently free" wording is neither a stated permanent tier nor a quantified grant — it can change; re-verify the rate-limit page.
- OVHcloud keyed access requires a payment method and is billed per token — only the anonymous lane is free.

**Sources**

- https://huggingface.co/Qwen/Qwen3-32B (32,768 native / 131,072 YaRN, tool calling, thinking modes, 32768 output)
- https://docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/ai-endpoints-capabilities (anonymous 2 RPM)
- https://docs.iflow.cn/zh-Hant/docs/ (model table, key steps, base URL)
- https://docs.iflow.cn/zh-Hant/docs/limitSpeed (currently-free statement, concurrency-1 limit)
