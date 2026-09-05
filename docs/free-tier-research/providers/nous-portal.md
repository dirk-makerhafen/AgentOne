---
name: Nous Portal
url: "https://portal.nousresearch.com/"
setup_instructions: |
  1. Register an account at https://portal.nousresearch.com/ and stay on the Free ($0) plan.
  2. Generate an API key in the portal.
  3. Point any OpenAI-compatible client at base URL https://inference-api.nousresearch.com/v1 with the key as Bearer token and a Portal-price-FREE model ID.
api_key_url: "https://portal.nousresearch.com/"
limits:
  requests:
    minute: 50
  tokens:
    minute: 500000
---

Nous Research's official API portal exposes 390 models (including its Hermes family) through an OpenAI-compatible API at `https://inference-api.nousresearch.com/v1`, with a standing $0 Free plan limited to free models.

**Free Tier:**

- **Free Tier:** Standing $0 Free plan — "Free models only, standard rate limits, $0 monthly credits" (official overview). Not a one-time grant; paid models require a subscription (Plus $20→$22 credits, Super $100→$110, Ultra $200→$220) or top-up.

**Free Models:**

- Free set is representative, verify live: the catalog at https://portal.nousresearch.com/models marks rows with Portal price FREE (rotating third-party free routes; observed 2026-09-05: LongCat 2.0, Laguna S/XS 2.1, Step 3.7 Flash, Solar Pro 4, Ling 3.0 Flash Fin, Ling 3.0 Flash Sante). `Hy3` is currently paid ($0.10 in / $0.42 out per 1M); `Ox Alpha` is no longer in the free list.
- Nous's own `Hermes-4-70B`, `Hermes-4-405B`, `Hermes-4.3-36B` (128K context, reasoning via system prompt) are documented API models but paid/discounted via Portal — not verified as free-tier models.

**Limits:**

- Free (official api-docs, quoted exactly): 50 RPM, 500,000 TPM.
- Requests/day and monthly token figures: unknown (not published).

**Notes:**

- Account required; API key required (Bearer). No credit card for Free (secondary-reported; official plan lists $0). Phone verification: unknown.
- Beta alternative auth: x402 protocol (Solana USDC) allows pay-per-request with no account or key (official api-docs).
- Per-model routing (OpenRouter/proprietary/secondary backends) can change; OpenRouter-specific request extensions may be ignored (official integration docs).
- Tool Gateway (managed tools) is paid-subscription-only; Hermes 4 models are officially not recommended inside Hermes Agent (weak tool-calling loop).
- Data-training policy: unknown — check Terms/Privacy.

**Sources**

- https://portal.nousresearch.com/
- https://portal.nousresearch.com/api-docs
- https://portal.nousresearch.com/models
- https://portal.nousresearch.com/manage-subscription
- https://hermes-agent.nousresearch.com/docs/integrations/nous-portal
- https://github.com/nejib1/Free-LLM
