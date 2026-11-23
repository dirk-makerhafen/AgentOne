---
name: GPT-OSS 20B
developer: OpenAI
canonical_id: openai/gpt-oss-20b
leaderboard_id: gpt-oss-20b
leaderboard_rank: 198
family: gpt-oss
context_window: 131072
reasoning: true
tool_call: true
structured_output: true
modalities:
  input:
  - text
  output:
  - text
open_weights: true
knowledge_cutoff: 2024-06
---

GPT-OSS 20B is OpenAI's smaller open-weight reasoning model (MoE, ~21B total / 3.6B active) for low-latency, local, or specialized agentic use. Official context window is 131072; InferX serves a capped 20K variant (see provider override).

**Capabilities:**

- Configurable reasoning effort (low/medium/high) with full chain-of-thought, tool/function calling (web search, code execution), and Structured Outputs (official model card).
- Text in / text out only (official: text-only models).
- Open weights under Apache 2.0 plus usage policy; MXFP4-quantized weights run within ~16GB memory.

**Notes:**

- Context: official OpenAI API docs list 131072 (blog: natively up to 128k); InferX catalogs 20,000 — recorded as a provider-level `context_window` override, not the card default. Copy the exact Model Name from the InferX Console (tenant-specific).
- InferX free models are rotating promotions ("Free · 100% off") — re-verify the endpoint-pricing page before use.
- OVHcloud anonymous lane covers catalog LLMs within the 2 RPM limit; keyed use requires a payment method and is not free.
- Skipped leads: Ollama Cloud catalogs `gpt-oss:20b` at paid per-token rates under monthly starter credits — not a standing free row. Pollinations (`gpt-oss`) and LLM7 (`gpt-oss`) expose a bare size-less ID whose 20B vs 120B size is indeterminable — not claimed on either card.
- `max_output_tokens`: fixtures disagree (65536 vs 131072) and no official per-request max confirmed — omitted. Temperature: fixture-inconsistent — omitted.

**Sources**

- https://openai.com/index/gpt-oss-model-card/ (official: Apache 2.0, text-only, reasoning, tool use, Structured Outputs, June 2024 cutoff)
- https://developers.openai.com/api/docs/models/gpt-oss-20b (official: 131072 context, Apache 2.0, Jun 01 2024 cutoff, 21B/3.6B active)
- https://openai.com/index/introducing-gpt-oss/ (official: MoE, tool use, natively up to 128k context, MXFP4)
- https://github.com/openai/gpt-oss (official: Apache 2.0, model weights/code)
- https://huggingface.co/openai/gpt-oss-20b (weights, MXFP4, reasoning effort)
- https://inferx.net/pricing/endpoints (official: `gpt-oss-20b` $0 promo row, 20,000 context)
- https://www.ovhcloud.com/en/public-cloud/ai-endpoints/catalog/ (official: catalog with `gpt-oss-20b`)
- https://docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/ai-endpoints-capabilities (official: anonymous 2 RPM per IP per model)
- raw/opencode-models-api/groq/model_gpt-oss-20b.json (capabilities/context — fixture-reported, discovery only)
- raw/opencode-models-api/ovhcloud/model_gpt-oss-20b.json (capabilities/context — fixture-reported, discovery only)
