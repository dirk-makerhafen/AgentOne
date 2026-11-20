---
name: Waterfall
url: "https://www.getwaterfall.org"
api_base: "https://api.getwaterfall.org/v1"
setup_instructions: |
  1. Sign in at https://getwaterfall.org/dashboard on the Free plan (no payment info) and create an API key (`wf-sk-...`).
  2. Point an OpenAI-compatible client at https://api.getwaterfall.org/v1.
  3. To stay strictly on zero-cost models, send `extra_body={"routing_strategy": "free_smart"}` with `model: "auto"`, or select an exact `-free` model id with the `exact` strategy.
  4. Browse the live free catalogue at https://getwaterfall.org/models or GET https://api.getwaterfall.org/api/v1/models.
api_key_url: "https://getwaterfall.org/dashboard"
---

Waterfall is an indie LLM router with a standing Free plan ($0/month, no card) and a curated, hourly-revalidated zero-cost pool. Verified 2026-11-20.

**Free Tier:**

- Free account + API key required; no payment info or card. Paid credit and x402 USDC paths are optional.
- No numeric RPM/RPD/TPM/TPD is published; the site describes "community rate limits — enough for development and hobby projects." No fixed daily token amount, no SLA.
- The free pool is dynamic. `free_smart` revalidates it hourly so a model that switches to paid is removed.

**Free Models:**

Live official catalogue on 2026-11-20 showed 62 zero-cost rows out of 445 and 11 catalog leads; 6 catalog IDs were confirmed with exact official IDs and capabilities:

- `nemotron-3-nano-omni-30b-a3b-reasoning-free` — 256K context, chat/vision/video/audio/tools/reasoning.
- `nemotron-3-super-120b-a12b-free` — 262,144 context, chat/tools/structured output/reasoning.
- `nemotron-3-super-120b-free` — 1M context, chat/tools/reasoning.
- `nemotron-3.5-lightning-free` — 1M context, chat/tools/reasoning.
- `laguna-s-2.1-free` — 262,144 context, chat/tools/reasoning.
- `lfm-2.5-2.6b-free` — 128K context, chat/tools/structured output/reasoning.
- Catalog leads not found live: `ling-3.0-flash-sante-free`, `ling-3.0-flash-vl-free`, `nex-n2.5-mini-free`, `nex-n2.5-pro-free`, `kimi-k3-nvidia-direct`. Related live alternatives include `ling-3.2-flash-free`, `kimi-k3.1-pro-nvidia-direct`, `laguna-xs-2.1-free`, `nemotron-3-ultra-550b-a55b-free`.

**Limits:**

- Omitted from frontmatter: no documented numerics. Do not infer from community limits or catalog rows.

**Notes:**

- Default strategy `free_first` "uses free tiers before paid fallbacks" and can escalate to paid. Pin `free_smart` or an exact `-free` model with `exact` for zero spend.
- Free routes are largely OpenRouter `:free` endpoints and NVIDIA NIM community models; third-party routing/data handling applies (see Trust Center).
- BYOK applies only to non-streaming requests; streaming uses Waterfall-shared credentials.
- A prior community report of downtime (freellmapi issue #1768) is not currently reproducible: site and API answered 200 on 2026-11-20. Long-term stability remains unverified.

**Sources**

- https://www.getwaterfall.org/
- https://getwaterfall.org/docs/
- https://getwaterfall.org/pricing/
- https://getwaterfall.org/strategies
- https://getwaterfall.org/models
- https://api.getwaterfall.org/api/v1/models
- https://getwaterfall.org/trust
- docs/free-tier-research/raw/freellmapi-catalog/platforms/waterfall.json (discovery lead, verified 2026-11-20)
