---
name: gpt-4o
family: gpt
series: gpt-4o
vision: true
supports_reasoning: false
supports_tool_call: true
open_weights: false
self_hosted: false
total_parameters: 200.0
active_parameters: 200.0
context_length: 128000
providers:
  - github-models
  - openrouter
---
GPT-4o is OpenAI's flagship multimodal model (May 2024), supporting text, vision, and audio input/output with 128K context. It's the strongest proprietary model available for free via GitHub Models (for existing users) and via OpenRouter (paid).

**Key Capabilities:**
- Native multimodal: text, image, audio in; text, audio out
- 128K token context window
- Full function/tool calling support
- Strong coding, reasoning, multilingual capabilities
- Real-time audio conversation (via Realtime API)
- Proprietary (closed weights)

**Free Access:**
- **GitHub Models**: `gpt-4o` — free tier with GitHub PAT (15 RPM, 150 RPD). *Note: GitHub Models closed to new users June 2026; existing users only.*
- **OpenRouter**: `openai/gpt-4o` — paid only (no free tier). ~$2.50/M input, $10/M output.

**Benchmarks:** MMLU ~88%, HumanEval ~90%, GPQA ~53%. Top-tier on coding, reasoning, multimodal tasks.

**Self-Hosting:** Not available (closed weights).

**License:** Proprietary (OpenAI API terms).

**Note:** Best available multimodal model. Free access only via GitHub Models (legacy users) or Azure AI Foundry (paid). For new users, consider Gemini 2.5 Flash (free, multimodal, 1M context) or GPT-4o-mini (cheaper paid). GPT-4o-mini also available free on GitHub Models.