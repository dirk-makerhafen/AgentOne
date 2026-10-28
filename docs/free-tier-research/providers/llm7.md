---
name: LLM7.io
url: "https://llm7.io"
api_base: "https://api.llm7.io/v1"
setup_instructions: |
  1. No signup or API key required for anonymous free tier.
  2. Call the OpenAI-compatible endpoint directly at https://api.llm7.io/v1.
  3. Optional: create an account for higher limits and persistent access.
api_key_url: "https://llm7.io"
limits:
  requests:
    minute: 15
    day: 10000
---

LLM7.io provides a free anonymous tier (no API key, no signup) with 15 RPM, 10K RPD. 30+ models including reasoning and vision variants.

**Free Tier:**

- Permanent free anonymous tier (no API key, no signup, no credit card).
- 15 RPM, 10,000 RPD.
- 30+ models (text, vision, reasoning).

**Free Models (verified 2026-09-05):**

- `deepseek-r1` — 131K context, 32K max output, text (reasoning).
- `deepseek-v3` — 128K context, 32K max output, text.
- `qwen3-235b-a22b` — 131K context, 32K max output, text.
- `qwen3-235b-a22b-instruct` — 131K context, 32K max output, text.
- `qwen3-30b-a3b` — 131K context, 32K max output, text.
- `qwen2.5-72b-instruct` — 131K context, 8K max output, text.
- `llama-3.3-70b-instruct` — 131K context, 8K max output, text.
- `gemma-2-27b-it` — 8K context, 8K max output, text.
- `mistral-nemo-12b-instruct` — 128K context, 8K max output, text.
- `phi-3.5-mini-instruct` — 128K context, 8K max output, text.
- +20 more models (vision, reasoning, embeddings).

**Limits:**

- 15 RPM, 10,000 RPD (anonymous tier).
- 429 when quota exceeded.
- Optional account for higher limits.

**Notes:**

- No account required for anonymous tier; no API key; no credit card.
- OpenAI-compatible: `https://api.llm7.io/v1`.
- Model IDs use simple names (no provider/ prefix).

**Sources**

- https://llm7.io (official site)
- https://api.llm7.io/v1/models (live model list)
- docs/free-tier-research/raw/awesome-free-llm-apis/LLM7.io.json (discovery snapshot, verified 2026-09-05)