---
provider: privatemode-ai
name: PrivateMode
free_verified: '2026-09-05'
models:
- provider_model_id: GLM-5.3
  model: glm-5.3
  conditions: Free tier 1M prompt + 1M completion tokens/mo (multiplier 1.0); account
    + org + key, no card
  verified: '2026-09-05'
- provider_model_id: gpt-oss-120b
  model: gpt-oss-120b
  conditions: Standing monthly quota (not a trial); 2.0x quota multiplier
  verified: '2026-09-05'
  limits:
    requests:
      minute: 20
    tokens:
      input:
        month: 500000
      output:
        month: 500000
limits:
  requests:
    minute: 20
  tokens:
    input:
      minute: 200000
      month: 1000000
    output:
      minute: 20000
      month: 1000000
---


# Free models offered by PrivateMode
