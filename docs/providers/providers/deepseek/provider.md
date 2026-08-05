---
name: DeepSeek
url: "https://api.deepseek.com/v1"
self_hosted: false
---
DeepSeek's official API platform provides direct access to DeepSeek models (V3, R1, V3.1) with $5 free credits on signup (email required). The platform is based in China with global CDN.

**Authentication:** API key (Bearer token). Get key at https://platform.deepseek.com/api_keys (email signup, no credit card for free credits).

**Free Tier:**
- $5 free credits on signup (never expire)
- Pay-as-you-go after credits exhausted
- Direct access to latest DeepSeek models first

**Paid Tier:** Competitive per-token pricing. DeepSeek-V3: ~$0.14/M input (cached), $0.28/M input, $1.10/M output. DeepSeek-R1: ~$0.55/M input, $2.19/M output.

**Key Features:**
- OpenAI-compatible API (`/chat/completions`, `/models`)
- Supports reasoning (R1), tool calling (V3/V3.1), JSON mode, structured output
- 128K-164K context on V3/V3.1
- Native DeepSeek API also available

**Models of Note:**
- `deepseek-chat` (DeepSeek-V3-0324) — 164K context, 671B MoE (37B active), tool calling
- `deepseek-reasoner` (DeepSeek-R1) — 64K context, 671B MoE, chain-of-thought reasoning
- `deepseek-v3.1` — 128K context, hybrid thinking/non-thinking, 671B MoE (37B active)

**Notes:** Best for earliest access to new DeepSeek models. Free credits sufficient for extensive testing. Also available free via OpenRouter (`deepseek/deepseek-chat-v3-0324:free`) and Together AI. Platform is China-based; consider data residency for production.