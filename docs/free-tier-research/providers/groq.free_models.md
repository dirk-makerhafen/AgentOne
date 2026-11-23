---
provider: groq
name: Groq
free_verified: '2026-09-05'
models:
- provider_model_id: qwen/qwen3.6-27b
  model: qwen3.6-27b
  conditions: Free plan; account + key, no card for Free tier
  verified: '2026-09-05'
  limits:
    requests:
      minute: 30
      day: 1000
    tokens:
      minute: 8000
      day: 200000
- provider_model_id: openai/gpt-oss-120b
  model: gpt-oss-120b
  conditions: Free Plan; account + key
  verified: '2026-09-05'
  limits:
    requests:
      minute: 30
      day: 1000
    tokens:
      minute: 8000
      day: 200000
- provider_model_id: qwen/qwen3.8-27b
  model: qwen3.8
  conditions: Free plan; account + key, no card for Free tier
  verified: '2026-09-05'
  limits:
    requests:
      minute: 30
      day: 1000
    tokens:
      minute: 8000
      day: 200000
limits:
  requests:
    minute: 30
    day: 1000
  tokens:
    minute: 8000
    day: 200000
---


# Free models offered by Groq
