---
provider: hetzner-inference
name: Hetzner Inference API
free_verified: '2026-09-05'
models:
- provider_model_id: Qwen/Qwen3.6-35B-A3B-FP8
  model: qwen3.6-35b-a3b
  conditions: Free while experimental; Hetzner customer account + token, no billing
  verified: '2026-09-05'
- provider_model_id: Qwen3.8-27B
  model: qwen3.8
  conditions: Free while experimental; Hetzner customer account + token, no billing
  verified: '2026-09-05'
limits:
  requests:
    minute: 10
  tokens:
    input:
      minute: 4000000
    output:
      minute: 100000
---


# Free models offered by Hetzner Inference API
