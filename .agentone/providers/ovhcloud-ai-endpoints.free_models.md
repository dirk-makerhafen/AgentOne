---
provider: ovhcloud-ai-endpoints
name: OVHcloud AI Endpoints
free_verified: '2026-09-05'
models:
- provider_model_id: Qwen3.5-397B-A17B
  model: qwen3.5-397b
  conditions: Anonymous tier; no account, key, or card; throttled per IP
  verified: '2026-09-05'
  limits:
    requests:
      minute: 2
- provider_model_id: gpt-oss-20b
  model: gpt-oss-20b
  conditions: Anonymous, no key, no card; roster rotates
  verified: '2026-09-05'
  limits:
    requests:
      minute: 2
- provider_model_id: gpt-oss-120b
  model: gpt-oss-120b
  conditions: Anonymous, no key, no card; roster rotates
  verified: '2026-09-05'
  limits:
    requests:
      minute: 2
- provider_model_id: Qwen3-32B
  model: qwen3-32b
  conditions: Anonymous tier; no account, key, or card; throttled per IP
  verified: '2026-09-05'
  limits:
    requests:
      minute: 2
limits:
  requests:
    minute: 2
---


# Free models offered by OVHcloud AI Endpoints
