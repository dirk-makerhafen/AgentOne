---
name: NVIDIA NIM
url: "https://build.nvidia.com"
api_base: "https://integrate.api.nvidia.com/v1"
setup_instructions: |
  1. Join the NVIDIA Developer Program at https://developer.nvidia.com/ (free, no credit card).
  2. Create an API key at https://build.nvidia.com/explore/discover (or via NGC).
  3. Call the OpenAI-compatible endpoint at https://integrate.api.nvidia.com/v1 with the key as Bearer token.
api_key_url: "https://build.nvidia.com/explore/discover"
limits:
  requests:
    minute: 40
    day: 10000
---

NVIDIA NIM provides free access to 100+ models with NVIDIA Developer Program membership. Rate-limited per model.

**Free Tier:**

- Free with NVIDIA Developer Program membership (free signup, no credit card).
- 40 RPM, 10,000 RPD per model.

**Free Models (verified 2026-09-05):**

- `google/gemma-4-31b-it` — 262K context, 8K max output, text + image + video.
- `nvidia/nemotron-3-ultra-550b-a55b` — 1M context, 262K max output, text (reasoning).
- `openai/gpt-oss-20b` — 131K context, 131K max output, text.
- +92 more models (text, image, video, speech, embeddings).

**Limits:**

- 40 RPM, 10,000 RPD per model.
- 429 when quota exceeded.
- Model availability subject to NVIDIA Developer Program terms.

**Notes:**

- Account required (NVIDIA Developer Program); API key required; no credit card.
- OpenAI-compatible: `https://integrate.api.nvidia.com/v1`.
- Live model catalog at https://build.nvidia.com/explore/discover.

**Sources**

- https://build.nvidia.com (official site)
- https://build.nvidia.com/explore/discover (model catalog & API keys)
- https://integrate.api.nvidia.com/v1/models (live model list)
- docs/free-tier-research/raw/awesome-free-llm-apis/NVIDIA NIM.json (discovery snapshot, verified 2026-09-05)