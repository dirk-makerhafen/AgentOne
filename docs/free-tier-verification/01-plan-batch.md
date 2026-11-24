# Task: plan the next free-tier verification batch

You are planning work, not researching it. Do not create or edit any file in
this task.

Work from the repository root.

## Read

- `~/.agentone/var/cache/free-tier/candidates/index.json`
- `~/.agentone/var/cache/free-tier/reviews/` (may not exist; if it does not,
  no provider has a review yet)
- for each provider, `.agentone/providers/<provider>/<provider>.json`

## What the data means

- `~/.agentone/var/cache/free-tier/candidates/index.json` is generated and lists
  every provider with free candidates.
- `~/.agentone/var/cache/free-tier/candidates/<provider>.json` holds candidates
  as `model`, `model_name`, `provider_model_id` and optional `limits`.
- `~/.agentone/var/cache/free-tier/reviews/<provider>.json` is the curated
  verdict file when it exists.
- `.agentone/providers/<provider>/<provider>.json` is the generated provider
  record. These keys may be agent-curated:
  `description`, `setup_instructions`, `url`, `api_key_url`,
  `default_api_key`, `doc`, `litellm_prefix`, `wire`, `research_sources`.

Never edit generated files in this task.

## Steps

1. Read the index. For every provider note its slug, name and
   `candidate_count`.
2. Note whether `~/.agentone/var/cache/free-tier/reviews/<provider>.json`
   exists and, if so, its `reviewed_at` date. A review older than 30 days is
   stale.
3. Open the provider file and note whether it is missing any of
   `description`, `setup_instructions` or `url`.
4. Prioritize in this order:
   a. no review file yet;
   b. review file older than 30 days;
   c. provider file missing curated metadata;
   d. largest `candidate_count`.
5. Select the next `N` providers. If `N` is not given, use 8.
6. Output one table:

   `provider | name | candidates | review | reviewed_at | missing metadata | priority reason`

7. Add the suggested run order and the task file for each provider:
   - missing metadata → `02-provider-metadata.md`
   - missing or stale review → `03-verify-free-tier.md`
   - both → metadata first, then verification.

Stop after the table. Do not research providers here.
