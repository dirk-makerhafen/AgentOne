---
provider: unorouter
name: UnoRouter
free_verified: '2026-09-05'
models:
- provider_model_id: dots-3-note-preview:free
  model: dots-3-note
  conditions: '`:free` suffix lane ($0/token, never touches balance); Discord/GitHub
    signup + key, no card; best-effort, pools drain/recover'
  verified: '2026-09-05'
- provider_model_id: deepseek-v4-pro:free
  model: deepseek-v4-pro
  conditions: :free lane; account + key, no card
  verified: '2026-09-05'
  limits:
    requests:
      minute: 1
- provider_model_id: nemotron-3.5-lightning:free
  model: nemotron-3.5-lightning-free
  conditions: :free lane; account + key, no card
  verified: '2026-10-28'
  limits:
    requests:
      minute: 1
- provider_model_id: glm-5.3-flash:free
  model: glm-5.3-flash
  conditions: :free lane; account + key, no card
  verified: '2026-09-05'
  limits:
    requests:
      minute: 1
- provider_model_id: gemma-4-31b-it:free
  model: gemma-4-31b-it
  conditions: :free lane; account + key, no card
  verified: '2026-09-05'
  limits:
    requests:
      minute: 1
- provider_model_id: glm-5.3:free
  model: glm-5.3
  conditions: :free lane; account + key, no card
  verified: '2026-09-05'
  limits:
    requests:
      minute: 1
- provider_model_id: nemotron-3.5-lightning:free
  model: nemotron-3.5-lightning
  conditions: :free lane; account + key, no card
  verified: '2026-09-05'
  limits:
    requests:
      minute: 1
- provider_model_id: gpt-oss-120b:free
  model: gpt-oss-120b
  conditions: :free lane; account + key, no card
  verified: '2026-09-05'
  limits:
    requests:
      minute: 1
- provider_model_id: qwen-3.8-27b:free
  model: qwen3.8
  conditions: :free lane; account + key, no card
  verified: '2026-09-05'
  limits:
    requests:
      minute: 1
- provider_model_id: deepseek-v4-flash:free
  model: deepseek-v4-flash
  conditions: :free lane; account + key, no card
  verified: '2026-09-05'
  limits:
    requests:
      minute: 1
limits:
  requests:
    minute: 1
---


# Free models offered by UnoRouter
