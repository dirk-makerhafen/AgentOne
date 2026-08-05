---
name: Alibaba Cloud Model Studio
url: "https://dashscope.aliyuncs.com/api/v1"
self_hosted: false
---
Alibaba Cloud Model Studio (DashScope) is Alibaba's official API platform providing access to the Qwen model family, including flagship models like Qwen3.5-397B-A17B, Qwen3-VL-235B, and Qwen3.5-Plus. Auth via `DASHSCOPE_API_KEY`.

**Authentication:** API key (`DASHSCOPE_API_KEY`). Get key at the Alibaba Cloud Model Studio console (email signup, free tier with credits).

**Free Tier:**
- Free tier with daily/monthly token quotas on many Qwen models
- New-user credits on signup
- Access to Qwen3.5-397B-A17B, Qwen3-VL, Qwen3.5-Plus (1M context hosted)

**Paid Tier:** Pay-as-you-go per token. Qwen3.5-Plus hosted 1M-context version available.

**Key Features:**
- OpenAI-compatible API (`/chat/completions`, `/models`)
- Multimodal (vision) support on Qwen3-VL and Qwen3.5
- Full function/tool calling
- Qwen3.5-Plus: 1M context, built-in tools, adaptive tool use

**Models of Note:**
- `qwen3.5-397b-a17b` / `Qwen3.5-Plus` — flagship MoE, 262K (1M ext), vision
- `qwen3-vl-235b-a22b` — flagship vision-language MoE, 256K
- `qwen3-235b-a22b` — previous generation flagship

**Notes:** Official first-party access to Qwen models with generous free tier. Best for earliest access and managed 1M-context hosting (Qwen3.5-Plus). Weights also on HuggingFace under Apache 2.0 for self-hosting.