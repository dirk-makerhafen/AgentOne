---
name: GitHub Models
url: "https://github.com/marketplace/models"
api_base: "https://models.github.ai/inference"
setup_instructions: |
  1. Have a GitHub account (free tier available).
  2. Generate a Personal Access Token (classic) at https://github.com/settings/tokens with `read:packages` scope, or use a fine-grained PAT with access to GitHub Models.
  3. Call the OpenAI-compatible endpoint at https://models.github.ai/inference with the token as Bearer token.
api_key_url: "https://github.com/settings/tokens"
limits:
  requests:
    minute: 50
    day: 1000
---

GitHub Models provides free access to 55+ models via GitHub Marketplace. All models are free during the preview period. Requires GitHub account and PAT.

**Free Tier:**

- Free access to all models in the catalog during preview (no credit card, GitHub account required).
- 50 RPM, 1,000 RPD (subject to change; preview limits).
- 55 models including GPT-4o, Llama, Mistral, Phi, DeepSeek, Cohere, Grok, Jamba.

**Free Models (verified 2026-10-27 from opencode fixtures):**

### OpenAI Models
- `openai/gpt-4o` — 128K context, 16K max output, vision, audio, tool calls
- `openai/gpt-4o-mini` — 128K context, 16K max output, vision, tool calls
- `openai/gpt-4.1` — 1M context, 32K max output, tool calls
- `openai/gpt-4.1-mini` — 1M context, 32K max output, tool calls
- `openai/gpt-4.1-nano` — 1M context, 32K max output, tool calls
- `openai/o1` — 200K context, 100K max output, reasoning, tool calls
- `openai/o1-mini` — 128K context, 65K max output, reasoning, tool calls
- `openai/o1-preview` — 128K context, 32K max output, reasoning, tool calls
- `openai/o3` — 200K context, 100K max output, reasoning, tool calls
- `openai/o3-mini` — 200K context, 100K max output, reasoning, tool calls
- `openai/o4-mini` — 200K context, 100K max output, reasoning, tool calls

### Meta Llama Models
- `meta/llama-3.3-70b-instruct` — 128K context, 33K max output, reasoning, tool calls, open weights
- `meta/llama-3.1-405b-instruct` — 128K context, 33K max output, tool calls, open weights
- `meta/llama-3.1-70b-instruct` — 128K context, 33K max output, tool calls, open weights
- `meta/llama-3.1-8b-instruct` — 128K context, 33K max output, tool calls, open weights
- `meta/llama-3-70b-instruct` — 8K context, 4K max output, tool calls, open weights
- `meta/llama-3-8b-instruct` — 8K context, 4K max output, tool calls, open weights
- `meta/llama-4-maverick-17b-128e-instruct-fp8` — 128K context, 33K max output, tool calls, open weights
- `meta/llama-4-scout-17b-16e-instruct` — 128K context, 33K max output, tool calls, open weights

### Microsoft Phi Models
- `microsoft/phi-4` — 128K context, 16K max output, reasoning, tool calls, open weights
- `microsoft/phi-4-reasoning` — 128K context, 16K max output, reasoning, tool calls, open weights
- `microsoft/phi-4-mini-instruct` — 128K context, 16K max output, tool calls, open weights
- `microsoft/phi-4-mini-reasoning` — 128K context, 16K max output, reasoning, tool calls, open weights
- `microsoft/phi-4-multimodal-instruct` — 128K context, 16K max output, vision, audio, tool calls, open weights
- `microsoft/phi-3.5-mini-instruct` — 128K context, 8K max output, tool calls, open weights
- `microsoft/phi-3.5-moe-instruct` — 128K context, 8K max output, tool calls, open weights
- `microsoft/phi-3.5-vision-instruct` — 128K context, 8K max output, vision, tool calls, open weights
- `microsoft/phi-3-medium-128k-instruct` — 128K context, 8K max output, tool calls, open weights
- `microsoft/phi-3-medium-4k-instruct` — 4K context, 4K max output, tool calls, open weights
- `microsoft/phi-3-mini-128k-instruct` — 128K context, 8K max output, tool calls, open weights
- `microsoft/phi-3-mini-4k-instruct` — 4K context, 4K max output, tool calls, open weights
- `microsoft/phi-3-small-128k-instruct` — 128K context, 8K max output, tool calls, open weights
- `microsoft/phi-3-small-8k-instruct` — 8K context, 8K max output, tool calls, open weights

### Mistral AI Models
- `mistralai/mistral-large-2411` — 128K context, 33K max output, tool calls
- `mistralai/mistral-medium-2505` — 128K context, 33K max output, tool calls
- `mistralai/mistral-small-2503` — 128K context, 33K max output, tool calls
- `mistralai/mistral-nemo` — 128K context, 33K max output, tool calls, open weights
- `mistralai/ministral-3b` — 128K context, 33K max output, tool calls, open weights

### Cohere Models
- `cohere/command-a` — 256K context, 64K max output, tool calls
- `cohere/command-r` — 128K context, 4K max output, tool calls
- `cohere/command-r-plus` — 128K context, 4K max output, tool calls
- `cohere/command-r-plus-08-2024` — 128K context, 4K max output, tool calls
- `cohere/command-r-08-2024` — 128K context, 4K max output, tool calls

### Other Models
- `ai21/jamba-1.5-large` — 256K context, 8K max output, tool calls
- `ai21/jamba-1.5-mini` — 256K context, 8K max output, tool calls
- `x-ai/grok-3` — 128K context, 33K max output, tool calls
- `x-ai/grok-3-mini` — 128K context, 33K max output, tool calls
- `deepseek-ai/DeepSeek-R1` — 128K context, 33K max output, reasoning, tool calls, open weights
- `deepseek-ai/DeepSeek-R1-0528` — 128K context, 33K max output, reasoning, tool calls, open weights
- `deepseek-ai/DeepSeek-V3-0324` — 128K context, 33K max output, tool calls, open weights
- `mai-ds-r1` — 128K context, 33K max output, reasoning, tool calls
- `meta/llama-3.2-11b-vision-instruct` — 128K context, 33K max output, vision, tool calls, open weights
- `meta/llama-3.2-90b-vision-instruct` — 128K context, 33K max output, vision, tool calls, open weights
- `codestral-2501` — 32K context, 8K max output, tool calls

**Limits:**

- 50 RPM, 1,000 RPD (preview limits, subject to change).
- Rate limits enforced per account (not per key).
- 429 when quota exceeded.

**Notes:**

- GitHub account required; PAT required; no credit card.
- OpenAI-compatible: `https://models.github.ai/inference`.
- Model IDs use provider/model format (e.g., `openai/gpt-4o`, `meta/llama-3.3-70b-instruct`).
- All models free during preview period; pricing may be introduced after GA.
- Live model catalog at https://github.com/marketplace/models.

**Sources**

- https://github.com/marketplace/models (official site)
- https://docs.github.com/en/github-models (documentation)
- https://models.github.ai/inference/models (live model list)
- docs/free-tier-research/raw/opencode-models-api/github-models/ (55 model fixtures, all free, verified 2026-10-27)