---
name: GPT-OSS 120B
developer: OpenAI
canonical_id: openai/gpt-oss-120b
leaderboard_id: gpt-oss-120b
leaderboard_rank: 172
family: gpt-oss
context_window: 131072
max_output_tokens: 65536
reasoning: true
tool_call: true
structured_output: true
temperature: true
modalities:
  input: [text]
  output: [text]
open_weights: true
providers:
  - name: Groq
    file: groq
    model_id: openai/gpt-oss-120b
    conditions: "Free Plan; account + key"
    limits:
      requests:
        minute: 30
        day: 1000
      tokens:
        minute: 8000
        day: 200000
    verified: "2026-09-05"
  - name: SambaNova Cloud
    file: sambanova
    model_id: gpt-oss-120b
    conditions: "Free tier; account + key, no card"
    limits:
      requests:
        minute: 20
        day: 20
      tokens:
        day: 200000
    verified: "2026-09-05"
  - name: FastRouter
    file: fastrouter
    model_id: openai/gpt-oss-120b:free
    conditions: "⚠ `:free` lane; org must hold a paid credit balance above $1 or free calls 402 (whether signup credits satisfy this is unverified)"
    limits:
      requests:
        day: 10
    verified: "2026-09-05"
  - name: UnoRouter
    file: unorouter
    model_id: gpt-oss-120b:free
    conditions: ":free lane; account + key, no card"
    limits:
      requests:
        minute: 1
    verified: "2026-09-05"
  - name: PrivateMode
    file: privatemode-ai
    model_id: gpt-oss-120b
    conditions: "Standing monthly quota (not a trial); 2.0x quota multiplier"
    limits:
      requests:
        minute: 20
      tokens:
        input:
          month: 500000
        output:
          month: 500000
    verified: "2026-09-05"
  - name: NVIDIA NIM
    file: nvidia-nim
    model_id: openai/gpt-oss-120b
    conditions: "Free tier"
    verified: "2026-09-05"
  - name: OVHcloud AI Endpoints
    file: ovhcloud-ai-endpoints
    model_id: gpt-oss-120b
    conditions: "Anonymous, no key, no card; roster rotates"
    limits:
      requests:
        minute: 2
    verified: "2026-09-05"
  - name: Cloudflare Workers AI
    file: cloudflare-workers-ai
    model_id: "@cf/openai/gpt-oss-120b"
    conditions: "Free lane exists but is not usable without payment"
    gate: "Paid billing (Workers Paid or prepaid AI Gateway credits) required to call it"
    notes: "Neuron budgets: ~31,818 in / 68,182 out neurons per M tokens"
    verified: "2026-09-05"
---

GPT-OSS 120B is OpenAI's flagship open-weight reasoning model and the most widely free-served model in this catalog (8 verified free routes). Max output varies by host (65K on Groq; up to 131K elsewhere).

**Capabilities:**

- Reasoning, tool/function calling, structured output, temperature control (fixture-reported, consistent across hosts).
- Text in / text out; 131K context.
- Open weights (Apache 2.0), self-hostable.

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Groq](../providers/groq.md) | `openai/gpt-oss-120b` | Free Plan; account + key | 30 RPM / 1,000 RPD / 8K TPM / 200K TPD | 2026-09-05 |
| [SambaNova Cloud](../providers/sambanova.md) | `gpt-oss-120b` | Free tier; account + key, no card | Provider-wide free tier: 20 RPM / 20 RPD / 200K TPD | 2026-09-05 |
| [FastRouter](../providers/fastrouter.md) | `openai/gpt-oss-120b:free` | ⚠ `:free` lane; org must hold a paid credit balance above $1 or free calls 402 | 10 req/day per org per model, UTC-midnight reset | 2026-09-05 |
| [UnoRouter](../providers/unorouter.md) | `gpt-oss-120b:free` | `:free` lane; account + key, no card | ~1 req/min per user + upstream caps | 2026-09-05 |
| [PrivateMode](../providers/privatemode-ai.md) | `gpt-oss-120b` | Standing monthly quota (not a trial) | 2.0× quota multiplier → effective ~500K tokens/month of the 1M+1M quota; 20 req/min provider-wide | 2026-09-05 |
| [NVIDIA NIM](../providers/nvidia-nim.md) | `openai/gpt-oss-120b` | Free tier ($0 fixture rows) | See provider file (catalog slugs churn) | 2026-09-05 |
| [OVHcloud AI Endpoints](../providers/ovhcloud-ai-endpoints.md) | `gpt-oss-120b` | Anonymous, no key, no card | 2 RPM provider-wide (representative snapshot; roster rotates) | 2026-09-05 |
| [Cloudflare Workers AI](../providers/cloudflare-workers-ai.md) | `@cf/openai/gpt-oss-120b` | ⚠ GATED — free lane exists but paid billing (Workers Paid or prepaid AI Gateway credits) is required to call it; not usable without payment | Neuron budgets: ~31,818 in / 68,182 out neurons per M tokens | 2026-09-05 |

**Notes:**

- Skipped leads: Ollama Cloud catalogs `gpt-oss:120b` at paid per-token rates under monthly starter credits — not a standing free row. Pollinations (`gpt-oss`) and LLM7 (`gpt-oss`) expose a bare size-less ID whose 20B vs 120B size is indeterminable — not claimed on either size card. AIHubMix documents only `gpt-oss-20b-free`, no 120B row.

**Sources**

- raw/opencode-models-api/groq/model_gpt-oss-120b.json (capabilities/context — discovery data)
- https://console.groq.com/docs/rate-limits
- https://docs.sambanova.ai/docs/en/models/rate-limits
- https://docs.privatemode.ai/rate-limits/
- https://www.ovhcloud.com/en/public-cloud/ai-endpoints/catalog/
