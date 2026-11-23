---
name: Qwen3.8-27B
developer: Alibaba (Qwen team)
canonical_id: qwen/qwen3.8-27b
leaderboard_id: qwen3.8-27b
leaderboard_rank: 43
family: qwen3
context_window: 262144
max_output_tokens: 131072
reasoning: true
tool_call: true
temperature: true
modalities:
  input:
  - text
  - image
  - video
  output:
  - text
open_weights: true
---

Qwen3.8-27B is Alibaba Qwen team's August 2026 generation of compact open-weight dense models (27B parameters, native multimodal) — "the most capable generation in the Qwen open-model family to date", outperforming Qwen3.7-Plus on coding and office workflows. Qwen3.6 (April 2026) is a separate, earlier generation with its own cards ([qwen3.6-27b](qwen3.6-27b.md), [qwen3.6-35b-a3b](qwen3.6-35b-a3b.md)).

**Capabilities:**

- Reasoning with thinking control (`reasoning_effort`), tool/function calling, temperature control (official model card and docs).
- Text + image + video in / text out (native vision-language); 262,144 native context, extendable to 1M via YaRN.
- Open weights under Apache 2.0 (Hugging Face `Qwen/Qwen3.8-27B`; official FP8 quant available).
- Agentic coding strength (official evals: Terminal Bench 2.1 73.0, OSWorld-Verified 84.3, SWE-bench Pro 61.7).

**Notes:**

- Excluded (paid, not free): InferX `Qwen3.8-27B-FP8` is 96% off but paid — despite discovery-fixture cost-0 rows.
- Qwen3.6 (April 2026) and Qwen3.8 (August 2026) are distinct generations sharing an architectural foundation — split into separate cards; see [qwen3.6-27b](qwen3.6-27b.md) / [qwen3.6-35b-a3b](qwen3.6-35b-a3b.md) for the earlier generation (Groq/InferX/Hetzner 3.6 rows).
- Do not confuse with `Qwen3-32B` ([card](qwen3-32b.md)), `Qwen3.5-397B-A17B` ([card](qwen3.5-397b.md)), or the Qwen3.8-2.4T-A95B flagship (separate bespoke licence).

**Sources**

- https://www.alibabacloud.com/help/en/model-studio/qwen3-8-27b (3.8 context limits: 1M window, 131072 max output)
- https://github.com/AlibabaCloud-Official/Qwen3.8-27B (262K native, YaRN to 1M, Apache 2.0)
- https://www.alibabacloud.com/blog/alibaba-unveils-qwen3-8-27b-and-releases-weights-of-qwen3-8-flagship-model_603463 (release, multimodal, Apache 2.0)
- https://huggingface.co/Qwen/Qwen3.8-27B (model card, eval tables vs 3.6)
- https://console.groq.com/docs/rate-limits (Free Plan figures)
- https://docs.hetzner.com/general/company-and-policy/experiments/inference/
