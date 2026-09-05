---
name: SKT A.X 4.0
url: "https://github.com/SKT-AI/A.X-4.0"
setup_instructions: |
  1. No signup required for guest access — use the officially published guest key below.
  2. Set base URL to https://guest-api.sktax.chat/v1 in any OpenAI-compatible client.
  3. Set the API key to the published guest key sktax-XyeKFrq67ZjS4EpsDlrHHXV8it.
  4. Call chat completions with model "ax4".
api_key_url: "https://github.com/SKT-AI/A.X-4.0/blob/main/apis/README.md"
default_api_key: public
limits:
---

Korean-specialized enterprise LLM (Qwen2.5-based) by SK Telecom, with a free anonymous guest API.

**Free Tier:**

- Official repo states "A.X 4.0 APIs are FREE now!" with a public key for anonymous users.

**Free Models:**

- `ax4` — A.X 4.0 chat model via the guest endpoint.

**Limits:**

- Unknown — no rate or quota figures are documented in the official API README; never assume limits.

**Notes:**

- Account required: no. API key required: yes, but published (guest key `sktax-XyeKFrq67ZjS4EpsDlrHHXV8it` from the official README — no signup). Payment/billing info required: no. Phone verification: no.
- Guest endpoint only; usage-based enterprise API plans and on-premise/hybrid deployment are described separately in the repo.

**Sources**

- https://github.com/SKT-AI/A.X-4.0/blob/main/apis/README.md
- https://github.com/SKT-AI/A.X-4.0
- https://huggingface.co/skt/A.X-4.0
