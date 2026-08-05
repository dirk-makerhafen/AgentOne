---
name: Google AI Studio
url: "https://generativelanguage.googleapis.com/v1beta/openai/"
self_hosted: false
---
Google AI Studio (Gemini Developer API) provides direct access to Google's Gemini models with a generous no-credit-card free tier. As of April 2026, Pro-series models (Gemini 2.5 Pro, 3.x Pro) are paid-only; the free tier covers Flash and Flash-Lite models with 1M token context windows.

**Authentication:** API key (Bearer token). Get key at https://aistudio.google.com/app/apikey (Google account only, no credit card).

**Free Tier:**
- **Gemini 2.5 Flash**: 10 RPM, 250K TPM, 1,500 RPD, 1M context
- **Gemini 2.5 Flash-Lite**: 15 RPM, 250K TPM, 1,000 RPD, 1M context
- **Gemini 2.0 Flash**: 15 RPM, 1M TPM, 1,500 RPD, 1M context
- **Gemini 3 Flash**: 10 RPM, 250K TPM, 1,500 RPD, 1M context
- **Gemini 3.1 Flash-Lite**: 15 RPM, 250K TPM, 1,000 RPD, 1M context
- **Gemma 2 27B**: 15 RPM, 1M TPM, 1,500 RPD, 8K context
- Free tier prompts may be used to improve Google products (opt out by enabling billing)

**Paid Tier:** Pay-as-you-go per token. Gemini 2.0 Flash at $0.075/M input is among cheapest on market.

**Key Features:**
- OpenAI-compatible API endpoint (`/v1beta/openai/chat/completions`)
- Native Gemini API also available (`/v1beta/models/{model}:generateContent`)
- Multimodal: text, image, audio, video input
- Supports function calling, JSON mode, structured output, code execution
- Configurable thinking levels (Gemini 3+)
- 1M token context on Flash models
- Code export from AI Studio playground

**Models of Note (Free):**
- `gemini-2.5-flash` — Hybrid reasoning, 1M context, strong coding/math
- `gemini-2.0-flash` — Highest free rate limits, 1M context, great value
- `gemini-3-flash` — Latest generation, configurable thinking
- `gemma-2-27b-it` — Open-weight, Apache 2.0

**Notes:** Best free tier for multimodal and long-context workloads. Pro models require billing. Data privacy: free tier data may be used for model improvement; enable billing to opt out.