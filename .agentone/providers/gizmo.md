---
name: Gizmo
url: "https://gizmoplatforms.com"
api_base: "https://api.gizmoplatforms.com/api/v1"
setup_instructions: |
  1. Sign up at https://gizmoplatforms.com (email, no card, choose the API starting point).
  2. Open Developers -> API keys and create a key.
  3. Point an OpenAI-compatible client at https://api.gizmoplatforms.com/api/v1.
  4. Call GET /api/v1/models and use an exact `:free` model id.
api_key_url: "https://gizmoplatforms.com/app/developers?tab=keys"
limits:
  requests:
    minute: 20
    month: 1000
---

Gizmo is a model marketplace/router with a standing Free plan: 1,000 zero-cost model API requests per calendar month (resets 1st UTC) and 20 API requests/minute. No card is required. Verified 2026-11-20.

**Free Tier:**

- 1,000 free-model API requests/month, shared account quota; 20 RPM (official docs/pricing).
- Account + API key required; Free plan needs no card. The $1 weekly usage allowance is for paid models; zero-cost models do not consume it.
- Admitted free requests count against the quota even when the upstream call fails.
- The platform fee is 5%; zero-cost models remain $0 within the quota.

**Free Models:**

- `nvidia/nemotron-3.5-lightning:free` — official model page confirms Free, 1M context, 66K max output, model-level Tool calling + Reasoning, open weights (routed via OpenRouter nvfp4). This is the only exact id confirmed from official docs.
- Catalog-reported ids whose official free display names exist (confirm exact wire ids via `GET /api/v1/models`): `nvidia/nemotron-3-ultra-550b-a55b:free`, `qwen/qwen3.8-27b:free`, `poolside/laguna-xs-2.1:free`, `poolside/laguna-s-2.1:free`.
- Official catalog also shows free display names from IncluSonai, Baidu, Particle AI and Recursive; those are expansion leads.

**Limits:**

- Frontmatter values are the Free plan's documented request caps.
- No published token quota for the free lane; do not infer one.

**Notes:**

- Model pages advertise capabilities, but the catalog quirk says the chat endpoint is text-only: tools, image/audio messages and structured output are unsupported, and undocumented fields return 400. This conflict needs a live probe before relying on tools.
- Both chat-completions and responses transports are documented for text; a Cloudflare Worker sits in the request path.
- Temporary reservations of full context + max output can make large-context calls fail early; free roster rotates.

**Sources**

- https://gizmoplatforms.com/developers
- https://gizmoplatforms.com/pricing
- https://gizmoplatforms.com/models/nvidia/nemotron-3.5-lightning%3Afree
- docs/free-tier-research/raw/freellmapi-catalog/platforms/gizmo.json (discovery lead, verified 2026-11-20)
