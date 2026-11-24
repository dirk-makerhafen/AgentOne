# Task: audit one free-tier review file

Check one curated review against the generated data and fix only the review
file. This is a consistency audit, not new research; if a fact is missing or
wrong, use the cited source or mark the entry `needs_followup`.

Work from the repository root. Set `PROVIDER` to the provider slug. If it is not
given, ask for it.

## Read

- `~/.agentone/var/cache/free-tier/candidates/<PROVIDER>.json` — generated candidates.
- `~/.agentone/var/cache/free-tier/reviews/<PROVIDER>.json` — the review under audit.
- `.agentone/providers/<PROVIDER>/<model>.json` for each referenced candidate.

## Fix only

`~/.agentone/var/cache/free-tier/reviews/<PROVIDER>.json`

Never edit the reviewed dataset in `.agentone/free/`, model files, the generated
fields of the provider file, or `docs/free-tier-research/`.

## Expected review shape

```json
{
  "schema_version": 1,
  "provider": "groq",
  "name": "Groq",
  "reviewed_at": "2026-11-24",
  "sources": [{ "id": "rate-limits", "url": "https://...", "title": "...", "accessed": "2026-11-24" }],
  "api_base": { "value": "https://...", "status": "verified", "verified": "2026-11-24", "source_ids": ["quickstart"] },
  "limits": { "rpm": 30, "rpd": 1000 },
  "models": {
    "gpt-oss-120b": {
      "verdict": "free",
      "provider_model_id": "openai/gpt-oss-120b",
      "conditions": "Free Plan; account + API key; no card required",
      "limits": { "tpm": 8000 },
      "verified": "2026-11-24",
      "source_ids": ["rate-limits"]
    },
    "gated-model": {
      "verdict": "payment_gated",
      "provider_model_id": "example/gated",
      "conditions": "Free lane exists but requires a paid plan",
      "gate": "Paid plan required",
      "verified": "2026-11-24",
      "source_ids": ["pricing"]
    },
    "bad-lead": {
      "verdict": "rejected",
      "reason": "Trial credit only",
      "verified": "2026-11-24",
      "source_ids": ["pricing"]
    }
  }
}
```

## Checks

1. `provider` matches the file slug.
2. `models` keys are exactly the `model` values in the generated free file:
   no missing, extra or misspelled keys.
3. Every `source_ids` value resolves to a top-level `sources` id.
4. Every `provider_model_id` equals the generated candidate's
   `provider_model_id` and appears in the model file as `provider_model_id`,
   in `provider_model_ids`, or in `aliases`.
5. Every `free` / `payment_gated` entry has `provider_model_id`, `conditions`,
   `verified` and at least one `source_ids` entry.
6. Every `rejected` / `needs_followup` entry has `reason`, `verified` and at
   least one `source_ids` entry.
7. `payment_gated` entries have `gate`; they are never plain `free`.
8. All `limits` use canonical flat keys only: `rps`/`rpm`/`rph`/`rpd`,
   `tps`/`tpm`/`tph`/`tpd`, `requests_per_month`, `tokens_per_month`,
   `concurrency`, or a qualified form such as `rpd_model` / `rpm_ip`. No `$`,
   `cost`, `credit`, `price`, `requests`, `tokens`, nested objects, or values
   derived by arithmetic.
9. Top-level `limits` exist only if the cited source says the quota applies to
   the whole free tier.
10. `api_base.status` is one of `verified`, `changed`, `unverifiable`, and its
    `source_ids` resolve when the status is `verified` or `changed`.
11. No `_generated_by` key exists in the review file.
12. `reviewed_at`, `verified` and `accessed` use today's or a recent date; flag
    stale reviews.

## Done

End with a pass/fail list and the exact fixes you made. If you changed a verdict
because evidence was insufficient, keep the entry `needs_followup` and explain
what to check.
