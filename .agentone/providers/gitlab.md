# GitLab Duo (GitLab.com) — Subscription-Required Access via GitLab Duo Add-on

> **Source**: opencode model fixtures (`raw/opencode-models-api/gitlab/`) — verified 2026-10-27; GitLab docs & pricing pages (docs.gitlab.com, about.gitlab.com/pricing/)

---

## 📋 Access Summary

| Aspect | Details |
|--------|---------|
| **Models in fixture** | 19 `duo-chat-*` variants (require paid Duo subscription or purchased credits) |
| **Auth** | `GITLAB_TOKEN` (Personal Access Token with `api` scope) |
| **API base** | `https://gitlab.example.com/api/v4/chat/completions` (Self-Managed) — proxied via AI Gateway |
| **OpenAI-compatible** | No native OpenAI endpoint; community adapters exist (e.g., `gitlab-duo-adapter`) |
| **Requires** | **Paid** GitLab Duo subscription ($19–39/user/mo) or purchased **GitLab Credits** pool |
| **Free tier** | **No Duo features by default** — can purchase credit pool; on-demand capped at $25K/mo |

---

## ⚠️ Not Free API Access (Per Catalog Criteria)

**GitLab Duo does not offer free API access** under this catalog's definition (see [AGENT.md](../AGENT.md#what-counts-as-free)):

- All 19 `duo-chat-*` models require an **active paid Duo subscription** (Premium $29/mo or Ultimate $99/mo per user) **or** a **purchased monthly commitment pool** of GitLab Credits.
- The Free tier ($0) explicitly has "**No Duo features by default**" — credits must be purchased.
- Per catalog rules: *models advertised as free but requiring a paid subscription* and *services where payment is required to obtain the API access* are **excluded** from free tier listings.

The opencode fixtures expose 19 models under the `duo-chat-*` namespace with `cost.input=0, cost.output=0`, but this zero marginal cost applies **only after** the subscription/credit purchase prerequisite is met.

## 📋 Model Catalog (Subscription Required)

All 19 models below have zero marginal token cost (cost.input=0, cost.output=0) **when you have an active paid GitLab Duo subscription or purchased credit pool**. Every model supports **reasoning** and **tool calling**.

| Model ID | Context | Family / Notes |
|----------|---------|----------------|
| `duo-chat-fable-5` | 1,000,000 | Anthropic Claude "Fable" family |
| `duo-chat-gpt-5-4-mini` | 400,000 | OpenAI GPT-5.4 mini |
| `duo-chat-gpt-5-2` | 400,000 | OpenAI GPT-5.2 |
| `duo-chat-sonnet-4-6` | 1,000,000 | Anthropic Claude Sonnet 4.6 |
| `duo-chat-opus-4-5` | 200,000 | Anthropic Claude Opus 4.5 |
| `duo-chat-gpt-5-4` | 1,050,000 | OpenAI GPT-5.4 |
| `duo-chat-sonnet-5` | 1,000,000 | Anthropic Claude Sonnet 5 |
| `duo-chat-gpt-5-4-nano` | 400,000 | OpenAI GPT-5.4 nano |
| `duo-chat-opus-4-8` | 1,000,000 | Anthropic Claude Opus 4.8 |
| `duo-chat-gpt-5-5` | 1,050,000 | OpenAI GPT-5.5 |
| `duo-chat-gpt-5-3-codex` | 400,000 | OpenAI GPT-5.3 Codex (coding-tuned) |
| `duo-chat-opus-4-7` | 1,000,000 | Anthropic Claude Opus 4.7 |
| `duo-chat-gpt-5-codex` | 400,000 | OpenAI GPT-5 Codex (coding-tuned) |
| `duo-chat-gpt-5-mini` | 400,000 | OpenAI GPT-5 mini |
| `duo-chat-opus-4-6` | 1,000,000 | Anthropic Claude Opus 4.6 |
| `duo-chat-haiku-4-5` | 200,000 | Anthropic Claude Haiku 4.5 |
| `duo-chat-sonnet-4-5` | 200,000 | Anthropic Claude Sonnet 4.5 |
| `duo-chat-gpt-5-2-codex` | 400,000 | OpenAI GPT-5.2 Codex (coding-tuned) |
| `duo-chat-gpt-5-1` | 400,000 | OpenAI GPT-5.1 |

**Model families represented**: OpenAI GPT-5.x (incl. mini/nano/codex), Anthropic Claude 4.x–5.x (Opus, Sonnet, Haiku, Fable).

---

## 💰 Pricing & Free Tier Mechanics

### GitLab Duo Tiers (per user/month)

| Tier | Price | Duo Features |
|------|-------|--------------|
| **Free** | $0 | **No Duo features by default** — can purchase credit pool |
| **Premium** | $29 | Duo Pro (non-agentic), 12 included credits/user/mo |
| **Ultimate** | $99 | Duo Enterprise (agentic), 24 included credits/user/mo |

### GitLab Credits (Usage-Based Billing)

Introduced in GitLab 18.7; Agent Platform on 18.8+.

- **Included credits**: Premium = 12/user/mo, Ultimate = 24/user/mo (non-shareable, reset monthly).
- **Monthly commitment pool**: Purchase a shared pool (tiered discounts, billed up-front, resets monthly, no rollover).
- **On-demand credits**: $1/credit after included + pool exhausted; must accept usage billing terms.
- **Free tier**: Can purchase monthly commitment pool; **on-demand capped at $25,000/month** per namespace.

### Credit Multipliers (calls per 1 credit)

| Model Tier | Example Models | Calls/Credit |
|------------|----------------|--------------|
| **Basic** | `codestral-2501`, `gemini-2.5-flash`, `gpt-5-mini`, `gpt-5-4-nano` | 8.0 |
| **Premium** | `claude-haiku-5.5`, `gpt-5.6-luna`, `minimax-m3`, `claude-4.5-haiku` | 6.7–16.7 |
| **Premium (high-end)** | `claude-opus-5.5`, `gpt-5.5`, `gpt-5.6-sol`, `kimi-k3` | 0.6–3.3 |

> The opencode fixtures expose **19 free models** under the `duo-chat-*` namespace. These map to the above upstream models and are included with any active Duo subscription or credit pool.

---

## 🔐 Authentication & Access

### Required

- **GitLab Personal Access Token** with `api` scope
- Token passed via `Authorization: Bearer <TOKEN>` header

### Environments

| Environment | Endpoint | Notes |
|-------------|----------|-------|
| **GitLab.com (SaaS)** | Internal-only (`/api/v4/chat/completions`) | Not publicly documented for external use; proxied via AI Gateway |
| **GitLab Self-Managed** | `https://<your-instance>/api/v4/chat/completions` | Requires feature flag `access_rest_chat` (16.7+); GA in 18.0 |

### Community OpenAI-Compatible Adapter

No native OpenAI endpoint exists. Community adapter:

- **gitlab-duo-adapter** (susmnavorasem/gitlab-duo-adapter) — FastAPI service exposing `/v1/chat/completions`, `/v1/models`, streaming via SSE
- Requires `GITLAB_TOKEN` + `GITLAB_URL` (default `https://gitlab.com`)
- Translates OpenAI requests → GitLab Duo Workflow System (DWS) WebSocket events

---

## ⚙️ Quick Start (Self-Managed + Adapter)

```bash
# 1. Clone community adapter
git clone https://github.com/susmnavorasem/gitlab-duo-adapter.git
cd gitlab-duo-adapter

# 2. Configure
cp .env.example .env
# Edit .env:
# GITLAB_TOKEN=glpat-xxxxxxxxxxxx  # PAT with 'api' scope
# GITLAB_URL=https://gitlab.com    # or your self-managed URL

# 3. Run
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.main

# 4. Test (OpenAI-compatible)
curl http://localhost:8080/v1/models
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"duo-chat-sonnet-4-5","messages":[{"role":"user","content":"Hello"}],"stream":false}'
```

---

## 📖 Key Documentation Links

| Topic | URL |
|-------|-----|
| GitLab Duo overview | https://docs.gitlab.com/user/gitlab_duo/ |
| GitLab Credits & billing | https://docs.gitlab.com/subscriptions/gitlab_credits/ |
| Duo Chat completions API (Self-Managed) | https://docs.gitlab.com/api/chat/ |
| Pricing & tiers | https://about.gitlab.com/pricing/ |
| Self-hosted models / BYOM | https://docs.gitlab.com/administration/gitlab_duo_self_hosted/ |
| Community adapter (OpenAI-compat) | https://github.com/susmnavorasem/gitlab-duo-adapter |

---

## ⚠️ Caveats & Limits

1. **No public OpenAI-compatible endpoint on GitLab.com** — the REST API is internal-only. Use Self-Managed with feature flag or the community adapter.
2. **Duo subscription or credit pool required** — Free tier without purchased credits has **no access** to Duo models.
3. **Model availability varies** — depends on GitLab instance config, subscription tier, and backend feature flags.
4. **Rate limits** — governed by credit consumption (multipliers above), not traditional RPM/TPM.
5. **Self-Managed minimum version** — 18.8 for Agent Platform, 18.9 for Free-tier trial with credits.
6. **Adapter limitations** — DWS is a workflow/agent system, not a raw LLM endpoint; tool use, safety checks, and quotas are server-side.

---

## 🔄 Related Providers

- **[github-copilot.md](github-copilot.md)** — similar "subscription-unlocks-free-models" pattern (25 free models with Copilot sub)
- **[openrouter.md](openrouter.md)** — aggregates many of the same upstream models (Claude, GPT, Gemini) via credits
- **[kenari.md](kenari.md)** — Indonesian gateway with free tier for some of the same model families

---

*Generated from opencode fixtures + GitLab public docs. Last verified 2026-10-27.*