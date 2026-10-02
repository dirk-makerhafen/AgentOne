---
name: Nous Portal
url: "https://portal.nousresearch.com/"
api_base: "https://inference-api.nousresearch.com/v1"
setup_instructions: |
  1. Register an account at https://portal.nousresearch.com/ and stay on the Free ($0/mo, $0 monthly credits) plan.
  2. Generate an API key in the portal.
  3. Point any OpenAI-compatible client at base URL https://inference-api.nousresearch.com/v1 with the key as Bearer token and a Portal-price-FREE model ID.
api_key_url: "https://portal.nousresearch.com/"
limits:
  requests:
    minute: 50
  tokens:
    minute: 500000
---

Nous Research's official API portal exposes 390 models (live count 2026-09-05, including its Hermes family) through an OpenAI-compatible API at `https://inference-api.nousresearch.com/v1`, with a standing $0 Free plan limited to free models.

**Free Tier:**

- **Free Tier:** Standing $0 Free plan — "Free models only, standard rate limits, $0 monthly credits" (official overview). Not a one-time grant; paid models require a subscription (Plus $20→$22 credits, Super $100→$110, Ultra $200→$220) or top-up.
- Free set verified live on the models page 2026-09-05 (Portal price FREE).

**Free Models:**

- Free set (Portal price FREE, live 2026-09-05): Meituan LongCat 2.0, Upstage Solar Pro 4, StepFun Step 3.7 Flash, Poolside Laguna S 2.1, Poolside Laguna XS 2.1, inclusionAI Ling 3.0 Flash Fin, inclusionAI Ling 3.0 Flash Sante (free). Rotating third-party free routes — verify live at https://portal.nousresearch.com/models.
- [`poolside/laguna-s-2.1`](../models/laguna-s-2.1.md) / [`laguna-xs-2.1`](../models/laguna-xs-2.1.md) free rows confirmed among the FREE set; paid duplicate routes for the same models also exist (e.g. Laguna S 2.1 at $0.07 in / $0.14 out per 1M) — send the FREE-priced route for free use.
- `Hy3` is currently paid ($0.10 in / $0.42 out per 1M); `Ox Alpha` is no longer in the free list.
- Nous's own `Hermes-4-70B`, `Hermes-4-405B`, `Hermes-4.3-36B` (128K context, reasoning via system prompt) are documented API models but paid/discounted via Portal — not verified as free-tier models.

**Limits:**

- Free: 50 RPM, 500,000 TPM. Official api-docs page is JS-rendered (not directly fetchable); figures corroborated 2026-09-05 by two independent secondaries citing official docs (dev.to 2026-08-02; TorchTree citing Portal API docs).
- Requests/day and monthly token figures: unknown (not published).

**Notes:**

- Account required; API key required (Bearer). No credit card for Free (secondary-reported; official plan lists $0). Phone verification: unknown.
- Beta alternative auth: x402 protocol (Solana USDC) allows pay-per-request with no account or key (official api-docs).
- Per-model routing (OpenRouter/proprietary/secondary backends) can change; OpenRouter-specific request extensions may be ignored (official integration docs).
- Tool Gateway (managed tools) is paid-subscription-only; Hermes 4 models are officially not recommended inside Hermes Agent (weak tool-calling loop).
- Data-training policy: unknown — check Terms/Privacy.

**Sources**

- https://portal.nousresearch.com/ (Free plan: free models only, $0 monthly credits)
- https://portal.nousresearch.com/api-docs (rate limits, x402 beta — JS-rendered; corroborated via secondaries below)
- https://portal.nousresearch.com/models (live FREE rows + 390-model count, checked 2026-09-05)
- https://portal.nousresearch.com/manage-subscription (Plus/Super/Ultra credit figures)
- https://hermes-agent.nousresearch.com/docs/integrations/nous-portal (base URL `https://inference-api.nousresearch.com/v1`, backend routing)
- https://dev.to/zackchew/nous-portal-explained-plans-models-tools-and-hermes-cloud-9hh (2026-08-02: Free $0/mo, 50 RPM / 500K TPM)
- https://github.com/nejib1/Free-LLM
