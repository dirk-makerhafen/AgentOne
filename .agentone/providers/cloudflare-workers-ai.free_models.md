---
provider: cloudflare-workers-ai
name: Cloudflare Workers AI
free_verified: '2026-09-05'
models:
- provider_model_id: '@cf/openai/gpt-oss-120b'
  model: gpt-oss-120b
  conditions: Free lane exists but is not usable without payment
  verified: '2026-09-05'
  gate: Paid billing (Workers Paid or prepaid AI Gateway credits) required to call
    it
  notes: 'Neuron budgets: ~31,818 in / 68,182 out neurons per M tokens'
limits:
  requests:
    minute: 300
---


# Free models offered by Cloudflare Workers AI
