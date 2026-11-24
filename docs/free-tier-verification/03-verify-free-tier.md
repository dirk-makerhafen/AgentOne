# Task: verify free-tier offerings for one provider

Turn one provider's generated candidate list into a curated review file. The
generated data is a set of **leads**, not proof. Verify each candidate against
official sources and record a verdict.

Work from the repository root. Set `PROVIDER` to the provider slug, for example
`groq`. If it is not given, ask for it before writing.

## Read

- `~/.agentone/var/cache/free-tier/candidates/<PROVIDER>.json` — generated
  candidates. Each has `model`, `model_name`, `provider_model_id` and optional
  `limits`.
- `.agentone/providers/<PROVIDER>/<PROVIDER>.json` — provider record (may have
  curated metadata).
- `.agentone/providers/<PROVIDER>/<model>.json` for every candidate `model`.
- `~/.agentone/var/cache/free-tier/reviews/<PROVIDER>.json` if it already
  exists; update it, do not duplicate it.

Write only `~/.agentone/var/cache/free-tier/reviews/<PROVIDER>.json`. This file
is curated and must not contain `_generated_by`. Never edit the reviewed dataset
in `.agentone/free/`, any model file, the generated fields of the provider file,
or `docs/free-tier-research/`.

## Discovery sources (leads only)

```text
* https://github.com/nejib1/Free-LLM
* https://github.com/CYBIRD-D/FREE-LLM-API-Provider
* https://freellms.org/providers/
* https://github.com/tashfeenahmed/freellmapi — public signed monthly catalog at
  https://api.freellmapi.co/v1/latest (~30 days behind the live feed)

OpenCode Zen free models via api_key "public":
https://raw.githubusercontent.com/anomalyco/opencode/refs/heads/dev/packages/web/src/content/docs/zen.mdx
```

These are leads only. Verify against official provider docs, pricing/free-tier
pages, public `/v1/models` responses, or a safe live request. Prefer the newest
reliable source; if sources conflict, say so and choose the newest authoritative
one.

## Free or not

Count as free when normal users can call the API without payment, even with
quotas, RPM/RPD limits, limited free tokens, selected free models, an account or
an API key.

Do not count as free: payment-required trials, one-time signup credits,
promotional credits with no standing tier, free web/chat without a free API,
models free only under a paid subscription, or services where payment is needed
to get API access.

Explicitly excluded examples from the original research:

- Volcengine ModelArk: 500K tokens/model one-time on registration.
- Alibaba Cloud Model Studio: 1M tokens/model one-time, 90-day expiry.
- Tencent Hunyuan: 1M tokens shared one-time, 1-year expiry.
- DeepSeek Platform: ~5M tokens one-time grant, no free-forever tier.
- iFlytek Spark main models: 2M/5M one-time packs, 1-year expiry; only `lite`
  is permanently free.

Never invent values. Never derive a limit by arithmetic. Ignore `$`/credit
budgets and never convert them into RPM/TPM numbers.

## Research per provider

1. Is the service still operational?
2. Is there a genuinely free API tier for normal users?
3. Are account, API key and payment/billing required?
4. Is the generated `api_base` still correct? Record `verified`, `changed` or
   `unverifiable` in the review file.
5. Which limits are documented for the whole free tier? Write top-level `limits`
   only when the source says the quota applies to all free models. Limits that
   are per model stay on that model.

## Research per candidate

1. Is this exact `provider_model_id` callable for free?
2. What are the exact conditions (account, key, tier, card, expiry)?
3. Which limits are documented for this model? Use canonical flat keys only.
4. If it is not usable for free, reject it with a reason: trial-only, one-time
   credit, chat-only, paid plan, wrong ID, stale/unavailable, or unmappable.
5. If it exists but is payment-gated, use `payment_gated` and record the gate.

`provider_model_id` must be copied exactly from the generated free candidate. If
the provider needs a different ID, record the exact string and explain it in
`notes`; never guess.

## Review file schema

`~/.agentone/var/cache/free-tier/reviews/<provider>.json`:

```json
{
  "schema_version": 1,
  "provider": "groq",
  "name": "Groq",
  "reviewed_at": "2026-11-24",
  "sources": [
    {
      "id": "rate-limits",
      "url": "https://console.groq.com/docs/rate-limits",
      "title": "Groq rate limits",
      "accessed": "2026-11-24"
    }
  ],
  "api_base": {
    "value": "https://api.groq.com/openai/v1",
    "status": "verified",
    "verified": "2026-11-24",
    "source_ids": ["quickstart"],
    "notes": "Optional note when status is changed or unverifiable"
  },
  "limits": {
    "rpm": 30,
    "rpd": 1000,
    "tpm": 8000,
    "tpd": 200000
  },
  "models": {
    "gpt-oss-120b": {
      "verdict": "free",
      "provider_model_id": "openai/gpt-oss-120b",
      "conditions": "Free Plan; account + API key; no card required",
      "limits": { "tpm": 8000 },
      "verified": "2026-11-24",
      "source_ids": ["rate-limits", "models"],
      "notes": "Optional combo-specific constraint"
    },
    "gated-model": {
      "verdict": "payment_gated",
      "provider_model_id": "example/gated",
      "conditions": "Free lane exists but requires a paid Workers plan",
      "gate": "Paid Workers plan required",
      "verified": "2026-11-24",
      "source_ids": ["pricing"]
    },
    "bad-lead": {
      "verdict": "rejected",
      "reason": "Trial credit only; no standing free API tier",
      "verified": "2026-11-24",
      "source_ids": ["pricing"]
    }
  }
}
```

Rules:

- `models` keys are exactly the `model` values from
  `~/.agentone/var/cache/free-tier/candidates/<provider>.json`. One entry per
  candidate, no extras.
- `verdict` is one of `free`, `payment_gated`, `rejected`, `needs_followup`.
- `free` and `payment_gated` entries need `provider_model_id`, `conditions`,
  `verified` and at least one `source_ids` entry. `payment_gated` also needs
  `gate`.
- `rejected` and `needs_followup` entries need `reason`, `verified` and at least
  one `source_ids` entry.
- Canonical flat limit keys only: `rps`/`rpm`/`rph`/`rpd`,
  `tps`/`tpm`/`tph`/`tpd`, `requests_per_month`, `tokens_per_month`,
  `concurrency`, and qualified forms such as `rpd_model` and `rpm_ip`. Never use
  nested `requests`/`tokens` or money keys.
- `source_ids` point to entries in top-level `sources`; do not repeat full URLs
  per model.
- Omit fields that cannot be verified. Never write `null` placeholders.
- Use today's date for `reviewed_at`, `verified` and `accessed`.

## Done

- The file is valid JSON and contains one entry per generated candidate.
- Every `source_ids` value resolves to a top-level `sources` id.
- No generated file was modified.
- Report verdict counts, the changed file, and the official sources used.
- If you cannot write files, output a unified diff instead.
