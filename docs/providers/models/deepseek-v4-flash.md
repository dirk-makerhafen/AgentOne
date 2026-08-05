---
name: deepseek-v4-flash
family: deepseek
series: deepseek-v4
vision: false
supports_reasoning: true
supports_tool_call: true
open_weights: true
self_hosted: true
total_parameters: 0.0
active_parameters: 0.0
context_length: 1000000
providers:
  - kenari
  - unorouter
  - openrouter
  - opencode-zen
---
DeepSeek V4 Flash is the latest fast/efficient model in the DeepSeek V4 family — a Mixture-of-Experts model with native reasoning support, tool calling, and a 1M token context window. The `:free` variant is available at zero cost through select aggregators.

**Key Capabilities:**
- MoE architecture (exact params undisclosed; V4 family is 671B/37B active like V3)
- 1M token context window
- Native reasoning with configurable effort (high, xhigh)
- Full function/tool calling support
- Structured output / JSON mode support
- Open weights (DeepSeek models are MIT licensed)
- Knowledge cutoff: May 2025

**Free Access:**
- **Kenari**: `deepseek-v4-flash:free` — free tier on Kenari router
- **UnoRouter**: `deepseek-v4-flash:free` — free tier on UnoRouter
- **OpenRouter**: Likely available as `deepseek/deepseek-v4-flash:free` (check OpenRouter free models collection)
- **OpenCode Zen**: `deepseek-v4-flash-free` — built-in free for opencode users

**Benchmarks:** Positioned as "fast DeepSeek V4 lane for economical reasoning, coding, and long-context work". Reasoning effort options (high, xhigh) allow trading latency for depth.

**Self-Hosting:** DeepSeek V4 weights expected to be released on Hugging Face under MIT license (like V3). Will require MoE-compatible inference (vLLM, SGLang, TRT-LLM).

**License:** MIT (expected, following DeepSeek V3 precedent).

**Note:** This is a very recent model (released April 2026). The `:free` suffix indicates zero-cost access via aggregator free tiers. The paid version (`deepseek-v4-flash`, `deepseek-v4-pro`) is available on the official DeepSeek API ($5 free credits on signup). Track OpenRouter's free models collection for availability.