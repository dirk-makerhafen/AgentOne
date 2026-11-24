# Task: QA a free-tier verification batch

Validate the providers reviewed in this batch before integration. Fix only
curated fields in provider files and files under
`~/.agentone/var/cache/free-tier/reviews/`.

Work from the repository root. If the batch provider list is not given, use every
review file changed in the current work, or ask for the list.

## Read

- `~/.agentone/var/cache/free-tier/candidates/index.json`
- `~/.agentone/var/cache/free-tier/candidates/<provider>.json` for each provider in the batch
- `.agentone/providers/<provider>/<provider>.json`
- `~/.agentone/var/cache/free-tier/reviews/<provider>.json`

## Fix only

- Allowlisted curated keys in `.agentone/providers/<provider>/<provider>.json`:
  `description`, `setup_instructions`, `url`, `api_key_url`,
  `default_api_key`, `doc`, `litellm_prefix`, `wire`, `research_sources`.
- Files under `~/.agentone/var/cache/free-tier/reviews/`.

Never edit generated fields, model files, the reviewed dataset in
`.agentone/free/`, or `docs/free-tier-research/`.

## Checks

1. Every provider file is valid JSON and only allowlisted curated fields
   changed. Generated keys (`_generated_by`, `catalog_updated_at`, `sources`,
   `model_count`, `provider`, `api_base`, …) are untouched.
2. Every review file is valid JSON and follows the review schema: `provider`,
   `name`, `reviewed_at`, `sources`, `api_base`, optional `limits`, and
   `models` keyed by candidate `model`.
3. Reviewed `model` values match the generated
   `~/.agentone/var/cache/free-tier/candidates/<provider>.json` exactly: no
   missing, extra or misspelled keys.
4. Every `source_ids` value resolves to a top-level `sources` id.
5. Every `provider_model_id` matches the generated candidate and appears in the
   matching model file.
6. Every `free` / `payment_gated` entry has `conditions`, `verified` and source
   IDs; `payment_gated` also has `gate`. Every `rejected` / `needs_followup`
   entry has `reason`, `verified` and source IDs.
7. No `free` verdict rests only on a generated signal, zero-cost fixture,
   FreeLLMAPI lead, or Awesome lead.
8. No money-derived or arithmetic-derived limit exists. All limits use canonical
   flat keys only.
9. Top-level `limits` exist only when the cited source says provider-wide.
10. Every source URL is official provider/pricing/docs/live-endpoint material;
    flag discovery-only URLs as a problem.
11. Dates are current, and no `_generated_by` key exists in a review file.
12. No unrelated generated file was modified.

## Done

Report, per provider: pass/fail, candidate count covered, verdict totals
(`free` / `payment_gated` / `rejected` / `needs_followup`), and files changed.
End with the overall batch result.
