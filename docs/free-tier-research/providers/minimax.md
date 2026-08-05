---
name: MiniMax
url: "https://api.minimax.io/v1"
self_hosted: false
---
MiniMax's official API platform provides access to the MiniMax model family, including the flagship MiniMax-M3 — a natively multimodal, 1M-context open-weight frontier model. Auth via `MINIMAX_API_KEY`.

**Authentication:** API key (`MINIMAX_API_KEY`). Get key at minimax.io.

**Free Tier:**
- Free access to MiniMax-M3 with free tier
- MiniMax-M3 also available free via OpenCode Zen and OpenRouter (`minimax/minimax-m3:free`)

**Paid Tier:** Pay-as-you-go per token. Inputs ≤512K billed at standard rate; >512K at long-context rate.

**Key Features:**
- OpenAI-compatible + Anthropic-compatible endpoints
- MiniMax Sparse Attention (MSA) for million-token context
- Native multimodality (text, image, video)
- Three reasoning modes (thinking param: enabled/adaptive/disabled)

**Models of Note:**
- `MiniMax-M3` — flagship 428B MoE (23B active), 1M context
- `MiniMax-M3-Preview` — preview variant (524K context)
- `MiniMax M2.7` — previous generation

**Notes:** First open-weight model combining frontier coding, million-token context, and native multimodality. Weights released on HuggingFace under MiniMax Community License.