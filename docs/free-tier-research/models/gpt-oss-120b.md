---
name: GPT-OSS 120B
developer: OpenAI
canonical_id: openai/gpt-oss-120b
leaderboard_id: gpt-oss-120b
leaderboard_rank: 133
family: gpt-oss
context_window: 131072
max_output_tokens: 65536
reasoning: true
tool_call: true
structured_output: true
temperature: true
modalities:
  input:
  - text
  output:
  - text
open_weights: true
---

GPT-OSS 120B is OpenAI's flagship open-weight reasoning model and the most widely free-served model in this catalog (8 verified free routes). Max output varies by host (65K on Groq; up to 131K elsewhere).

**Capabilities:**

- Reasoning, tool/function calling, structured output, temperature control (fixture-reported, consistent across hosts).
- Text in / text out; 131K context.
- Open weights (Apache 2.0), self-hostable.

**Notes:**

- Skipped leads: Ollama Cloud catalogs `gpt-oss:120b` at paid per-token rates under monthly starter credits — not a standing free row. Pollinations (`gpt-oss`) and LLM7 (`gpt-oss`) expose a bare size-less ID whose 20B vs 120B size is indeterminable — not claimed on either size card. AIHubMix documents only `gpt-oss-20b-free`, no 120B row.

**Sources**

- raw/opencode-models-api/groq/model_gpt-oss-120b.json (capabilities/context — discovery data)
- https://console.groq.com/docs/rate-limits
- https://docs.sambanova.ai/docs/en/models/rate-limits
- https://docs.privatemode.ai/rate-limits/
- https://www.ovhcloud.com/en/public-cloud/ai-endpoints/catalog/
