---
name: Qwen3.5-397B-A17B
developer: Alibaba (Qwen team)
canonical_id: qwen/qwen3.5-397b-a17b
leaderboard_id: qwen3.5-397b-a17b
leaderboard_rank: 41
family: qwen3.5
context_window: 262144
reasoning: true
tool_call: true
temperature: true
modalities:
  input: [text, image]
  output: [text]
open_weights: true
providers:
  - name: OVHcloud AI Endpoints
    file: ovhcloud-ai-endpoints
    model_id: Qwen3.5-397B-A17B
    conditions: "Anonymous tier; no account, key, or card; throttled per IP"
    limits:
      requests:
        minute: 2
    verified: "2026-09-05"
---

Qwen3.5-397B-A17B is the first open-weight model of Alibaba's Qwen3.5 series: a 397B-total / 17B-active MoE (hybrid Gated DeltaNet + attention) and native vision-language model under Apache 2.0, with 262,144 native context extendable to ~1M via YaRN.

**Capabilities:**

- Reasoning (thinking mode; `reasoning-parser qwen3` in vLLM/SGLang recipes), agentic workflows, temperature control (official model card and announcement).
- Text + image in / text out; 262,144 native context (1,010,000 with YaRN).
- Open weights (Apache 2.0; Hugging Face `Qwen/Qwen3.5-397B-A17B`).

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [OVHcloud AI Endpoints](../providers/ovhcloud-ai-endpoints.md) | `Qwen3.5-397B-A17B` | Anonymous tier; no account, key, or card | 2 req/min per IP per model; roster rotates | 2026-09-05 |

**Notes:**

- Single-provider card: StreamLake Vanchin lists a `Qwen3.5-397B-A17B`-style base model, but its provider-side ID is always a per-user endpoint ID and per-model free eligibility is login-gated — no 1:1 card row assertable, so it is excluded.
- OVHcloud keyed access requires a payment method and is billed per token — only the anonymous lane is free.
- Do not confuse the open-weight checkpoint (262K native) with the hosted Qwen3.5-Plus sibling (1M default context, built-in tools, adaptive tool use).

**Sources**

- https://huggingface.co/Qwen/Qwen3.5-397B-A17B (397B/17B MoE, 262,144 native, 1,010,000 YaRN, agentic/thinking)
- https://www.alibabacloud.com/blog/qwen3-5-towards-native-multimodal-agents_602894 (release announcement, hybrid architecture, Apache track)
- https://docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/ai-endpoints-capabilities (anonymous 2 RPM)
