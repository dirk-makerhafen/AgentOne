---
name: Ollama
api_base: "http://localhost:11434/v1/"
url: "https://ollama.com"
litellm_prefix: ollama
is_local: true
setup_instructions: |
  Install Ollama locally and pull the models you want (`ollama pull <model>`).
  The local daemon serves an OpenAI-compatible API on port 11434.
---

Ollama runs models on the local machine. Local providers can still serve cloud
models — those are distinguished per-model via `is_cloud`.
