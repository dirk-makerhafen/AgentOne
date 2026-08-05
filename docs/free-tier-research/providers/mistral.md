---
name: Mistral AI
url: "https://api.mistral.ai/v1"
self_hosted: false
---
Mistral AI's official API platform (Le Chat / La Plateforme) provides access to the full Mistral model family, including the flagship Mistral Large 3. Offers a generous free tier with no credit card required. Auth via `MISTRAL_API_KEY`.

**Authentication:** API key (`MISTRAL_API_KEY`). Get key at console.mistral.ai (email signup, no credit card).

**Free Tier:**
- Free "Experiment" plan: ~1B tokens/month, 1 request/second, no credit card
- Prompts may be used to improve models
- Access to all Mistral models including Large 3

**Paid Tier:** Pay-as-you-go per token. Pro and Scale plans for higher throughput and data privacy.

**Key Features:**
- OpenAI-compatible API (`/chat/completions`, `/models`)
- Native function calling and JSON output (Large 3)
- Vision (image input) on Large 3
- Multilingual (dozens of languages)

**Models of Note:**
- `mistral-large-3` (`mistralai/mistral-large-3-675b-instruct-2512`) — flagship 675B granular MoE (41B active), 256K context, vision
- `mistral-medium-3` — mid-tier
- `ministral-3` — edge/dense models (3B/8B/14B)

**Notes:** Generous free tier ideal for prototyping. Mistral Large 3 is Apache 2.0 licensed for full self-hosting freedom. Best-in-class agentic function calling.