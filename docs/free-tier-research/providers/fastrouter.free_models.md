---
provider: fastrouter
name: FastRouter
free_verified: '2026-09-05'
models:
- provider_model_id: nvidia/nemotron-3-super:free
  model: nemotron-3-super-120b-a12b
  conditions: ⚠ `:free` lane; org must hold a paid credit balance above $1 or free
    calls 402 (whether signup credits satisfy this is unverified)
  verified: '2026-09-05'
  limits:
    requests:
      day: 10
- provider_model_id: nvidia/nemotron-3-nano-30b:free
  model: nemotron-3-nano-30b-a3b
  conditions: ⚠ `:free` lane (provider ID differs from card default); org must hold
    a paid credit balance above $1 or free calls 402
  verified: '2026-09-05'
  limits:
    requests:
      day: 10
- provider_model_id: openai/gpt-oss-20b:free
  model: gpt-oss-20b
  conditions: ⚠ `:free` lane; org must hold a paid credit balance above $1 or free
    calls 402 (whether signup credits satisfy this is unverified)
  verified: '2026-09-05'
  limits:
    requests:
      day: 10
- provider_model_id: openai/gpt-oss-120b:free
  model: gpt-oss-120b
  conditions: ⚠ `:free` lane; org must hold a paid credit balance above $1 or free
    calls 402 (whether signup credits satisfy this is unverified)
  verified: '2026-09-05'
  limits:
    requests:
      day: 10
limits:
  requests:
    day: 10
---


# Free models offered by FastRouter
