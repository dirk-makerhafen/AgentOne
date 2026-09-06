Your goal is to find **currently available free LLM API resources** and maintain a clean, accurate provider list in `providers/` plus a cross-referenced model catalog in `models/`.

Your task is to research these discovery sources:

* https://github.com/nejib1/Free-LLM
* https://github.com/CYBIRD-D/FREE-LLM-API-Provider
* https://freellms.org/providers/

Opencode (popular agent harness) also often has for a short time very good models for free via opencode zen, using their api_key "public" , easy extractable via https://raw.githubusercontent.com/anomalyco/opencode/refs/heads/dev/packages/web/src/content/docs/zen.mdx

For every provider you find that offers a **genuinely usable free LLM API**, create or update a Markdown file in:

`providers/<provider-name>.md`

For every model that is free through at least one verified provider, create or update a model card in:

`models/<model-name>.md`

Each model card captures the model facts once (developer, context, capabilities) and carries a providers table showing, per provider, the provider-side model ID plus the provider+model specific free conditions and limits — so for each model you can see who serves it for free under what terms.

## Research

The three sources are **discovery sources, not authoritative sources**. Do not blindly copy them.

For every provider:

1. Find the provider's official website and API documentation.
2. Verify that free API access is currently available.
3. Determine:

   * whether an account is required
   * whether an API key is required
   * whether payment/billing information is required
   * API endpoint
   * free models
   * request limits
   * token limits
   * context limits
   * other important restrictions
4. Prefer official documentation and pricing/free-tier pages if available.
5. If sources disagree, investigate and use the most recent/reliable information.
6. Do not infer or guess limits.

A provider discovered outside the three lists may also be added if it has a verifiable free API.

## Data Extraction Scripts

Run extraction scripts to download data into `raw/`, these files, especially the opencode data provides valuable structured information about providers and models.

```bash
# Source 1: awesome-free-llm-apis data.json (24 free LLM providers)
python3 scripts/generate_from_awesome_apis.py

# Source 2: opencode test fixtures (120 providers, 2000+ models)
python3 scripts/generate_from_opencode_fixtures.py

# Source 3: Leaderboard generation. do not edit. creates raw/leaderboard.csv
python3 scripts/generate_leaderboard.py

```

## What counts as free

Include services that provide usable LLM API inference without requiring payment, even if they have:

* daily/monthly quotas
* RPM/RPD limits
* limited free tokens
* only selected free models
* account registration
* API-key registration

Do **not** treat the following as free API access:

* free trials requiring payment
* low one-time signup credits
* promotional credits unless clearly useful as a free offering
* free web/chat access with no free API
* models advertised as free but requiring a paid subscription
* services where payment is required to obtain the API access

Clearly distinguish free API access from free application/web access.

## Files

Create one canonical file per provider:

`providers/<provider-name>.md`

Create one canonical file per model:

`models/<model-name>.md`

Check for an existing file first. If it exists, update it rather than creating a duplicate.

Use stable, human-readable filenames.

Do not create separate provider files for individual models — models live in `models/`, not `providers/`.

## File format

Use this structure:

```markdown
---
name: Provider Name
url: "https://..."

setup_instructions: |
  Explain exactly how a new user obtains access.

api_key_url: "https://..."

default_api_key: public

limits:
  requests:
    minute: 20
    day: 1000
  tokens:
    minute: 100000
    day: 1000000
---

Short factual description of the provider and its free offering.

**Free Tier:**

- ...

**Free Models:**

- `model-name` — context, capabilities, relevant limitations
- `model-name` — ...

**Limits:**

- ...

**Notes:**

...

**Sources**

- https://...
- https://...
```

Adapt the fields when necessary. **Never invent missing values.**

## Frontmatter

Keep frontmatter concise and machine-readable.

Use:

* `name`
* `url`
* `setup_instructions`
* `api_key_url`
* `default_api_key`
* `limits`

`default_api_key: public` means that the documented free access method does not require a user-specific API key. Do not use it merely because obtaining a key is easy.

## Limits

Represent usage limits using a nested `limits` object.

Supported categories:

* `requests`
* `tokens`

Supported periods:

* `second`
* `minute`
* `hour`
* `day`
* `week`
* `month`

Example:

```yaml
limits:
  requests:
    second: 2
    minute: 30
    hour: 500
    day: 1000
    week: 5000
    month: 20000

  tokens:
    second: 5000
    minute: 100000
    hour: 1000000
    day: 5000000
    week: 20000000
    month: 50000000
```

Only include limits that are actually documented or reliably verified.

**Never derive additional limits.**

If the provider says `1000 requests/day`, record only:

```yaml
limits:
  requests:
    day: 1000
```

Do not calculate hourly/minute limits from it.

Omit unknown limits rather than guessing.

### Token limits

Distinguish between:

* input tokens
* output tokens
* combined input/output tokens

If the provider distinguishes them:

```yaml
limits:
  tokens:
    input:
      minute: 100000
      day: 1000000
    output:
      minute: 50000
      day: 500000
```

If the limit is combined:

```yaml
limits:
  tokens:
    minute: 100000
    day: 1000000
```

If it is unclear, do not guess. Explain the ambiguity in the document.

### Quotas vs rate limits

Use the same structure for fixed quotas and rate limits.

For example:

```yaml
limits:
  requests:
    minute: 20
    day: 1000
  tokens:
    month: 10000000
```

Explain unusual quota semantics in the document body.

### Model-specific limits

The frontmatter `limits` should represent provider-wide/default limits.

If limits differ by model, document them in the body instead:

```markdown
**Model-specific limits:**

- `model-a`: 10 RPM, 500K tokens/day
- `model-b`: 30 RPM, 1M tokens/day
```

Do not put one model's limits into the provider-wide frontmatter.

### Per-request limits

Do not put context windows or maximum tokens per request into `limits`.

For example:

* 128K context
* 8192 maximum output tokens
* 1M maximum input tokens per request

These are model/request constraints, not usage-over-time limits. Document them under the relevant model.

## Models

List models that are **actually free through the API**.

Do not list every model offered by the provider if only some are free.

For important free models, document when reliably available:

* model ID
* context window
* reasoning
* tool/function calling
* multimodal support
* other significant limitations

Do not invent capabilities.

## Model files

Create a card for a model when it is free through at least one verified provider. Prioritize models free at two or more providers (the cross-provider comparison is the point of the catalog).

### Filenames

- One canonical file per model: `models/<model-slug>.md`, lowercase slug (e.g. `models/gpt-oss-120b.md`, `models/glm-4.7-flash.md`).
- Strip access suffixes from the filename: no `:free` / `-free` (e.g. `gemma-4-31b-it.md`, not `gemma-4-31b-it-free.md`).
- Omit the vendor prefix unless needed for uniqueness (e.g. `nemotron-3-nano-30b-a3b.md`, not `nvidia-nemotron-...md`).
- The leaderboard (`raw/rankings/leaderboard.csv`, columns `Rank,Model ID,Name,Organization,Score`) is the reference for what counts as a "top-level" model. One leaderboard entry = one model file: if the CSV lists versions as separate Model IDs (e.g. `laguna-s-2.1` vs `laguna-xs-2.1`, `glm-5.3` vs `glm-5.2`, `qwen3.6-27b` vs `qwen3.6-35b-a3b`), they get separate cards (`models/laguna-s-2.1.md`, `models/laguna-xs-2.1.md`), because free availability varies per version. Two entries in the leaderboard ⇒ two card files; never merge multiple leaderboard entries into one "family" card.
- Record the mapping in frontmatter as `leaderboard_id:` (exact Model ID string from the CSV) and `leaderboard_rank:` (exact `Rank` column value, integer). If the CSV has several spellings for the same model (e.g. `inkling` vs `Inkling Small`, `inkling-small`), use the canonical lowercase `Model ID` and note the alias collision in the card. Ranks/scores otherwise live in `raw/rankings/` — only the `leaderboard_rank` integer goes into the card; do not copy score tables into cards (the CSV is a stale snapshot; the generator is currently broken, see line 57).
- Missing from the leaderboard: if no CSV entry denotes the card's model but you have reason to believe it is a top-level model (large parameter count, recent release, frontier-class), research public benchmarks and record an **estimated** rank as `leaderboard_rank_estimated: "~N"` (note the basis/source and date in the card). Example: `agnes-2.5-flash` is newer than the leaderboard snapshot, so it gets an estimated rank.
- Do **not** estimate ranks for models clearly not top-level: names carrying a small-model size suffix (e.g. `-8b`, `-2.6b`, `-10b` or models that are ≥1 year old, or are clearly superseeded by a newer version. We dont need these models, and thus these models dont need a model card at all. 

### File format

Use this structure:

```markdown
---
name: Model Display Name
developer: Organization
canonical_id: vendor/model-slug
leaderboard_id: leaderboard-model-id
leaderboard_rank: 53
family: model-family
context_window: 131072
max_output_tokens: 32768
reasoning: true
tool_call: true
structured_output: true
temperature: true
modalities:
  input: [text, image]
  output: [text]
open_weights: true
knowledge_cutoff: "2025-05"
providers:
  - name: Provider Name
    file: provider-file-slug
    model_id: id-on-that-provider
    conditions: who gets it free, what is required
    limits:
      requests:
        minute: 1
    verified: "2026-09-05"
---

Short factual description of the model.

**Capabilities:**

- ...

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Provider Name](../providers/<file>.md) | `id-on-that-provider` | who gets it free, what is required | limits applying to this provider+model combo | 2026-09-05 |
| ... | ... | ... | ... | ... |

**Notes:**

- ...

**Sources**

- https://...
- https://...
```

Frontmatter is the machine-readable source of truth, including the `providers` list. The markdown table mirrors it 1:1 for human reading — same providers, same order, same values. When updating one, update the other. Omit any frontmatter field that cannot be verified; never invent values. Fixture-derived facts (`raw/opencode-models-api/`) are discovery data: usable for capabilities/context with a `(fixture-reported, verify live)` flag, never as the sole source for free availability.

### Model frontmatter fields

Model-card frontmatter adds these per-model keys alongside `name`/`developer`/`canonical_id`:

- `leaderboard_id` — exact `Model ID` from `raw/rankings/leaderboard.csv` when an entry denotes this model; see Filenames above for the two-entries-two-cards rule.
- `leaderboard_rank` — integer `Rank` column value from the CSV for that `leaderboard_id`.
- `leaderboard_rank_estimated` — only when there is no CSV entry but the model is plausibly top-level: an approximate rank (e.g. `"~25"`) derived from public benchmark aggregates, with the basis/source and date noted in the card body. Never estimated for small-model names (e.g. `-8b`) or models ≥1 year old.
- `family` — short slug grouping version variants (used in cross-reviews).

Both rank keys are presentation-only: they never change free-access rows.

### Providers entry schema

Each `providers` entry:

- `name` — provider display name (matches its `providers/` file `name`).
- `file` — slug mapping to `providers/<file>.md` (no path, no extension).
- `model_id` — exact string(s) to send as `model` on that provider; a list when versions/variants differ per host.
- `conditions` — concise string: who gets it free, what is required, any gating (trial-use, promo expiry).
- `limits` — only limits specific to this provider+model combo, using the same nested `requests`/`tokens` shape as provider frontmatter. Omit entirely when no combo-specific numerics are documented.
- `context_window` / `max_output_tokens` — only when this provider serves the model with different values than the card default (e.g. a capped variant).
- `gate` — reason string for payment-gated rows (renders as a ⚠ table row, never a plain free row).
- `notes` — combo-specific constraints that fit neither `limits` nor overrides (e.g. neuron budgets, context-tiered pricing).
- `verified` — date of last verification (`YYYY-MM-DD`).

### Providers table rules

- One row per provider serving this model for free. Link the provider name to its `providers/` file.
- Every table row corresponds 1:1 to a frontmatter `providers` entry (same order); frontmatter is authoritative for tooling.
- `Provider-side ID` is the exact string to send as `model` on that provider (e.g. `deepseek-v4-flash:free` on UnoRouter vs `deepseek-v4-flash` on DeepSeek's own platform).
- `Free conditions` states what the user needs (account, key, tier, no card) and any gating (trial-use, promo expiry, paid billing required).
- `Model-specific limits` holds only limits applying to this provider+model combination (per-model RPM, quota multipliers, neuron budgets). Provider-wide defaults stay in the provider file — reference them, do not duplicate numbers that drift.
- Rows that are payment-gated (e.g. free lane requiring paid billing) may be listed only with an explicit ⚠ flag explaining the gate — never as plain free rows.
- Fixture-observed but file-unverified rows do not go in the table; mention them under **Notes** as re-verification leads.

### Cross-linking

- `providers/` and `models/` are maintained together: when you add a free model to a provider file, add/update its model card table row; when you add a model card, make sure each listed provider file documents that model ID.
- Provider-file model bullets SHOULD link to the model card (`[id](../models/<slug>.md)`) when one exists; backfill links opportunistically during verification passes.

## Accuracy

Every important, changeable claim must be supported by a source.

This includes:

* free-tier availability
* models
* model IDs
* rate limits
* token quotas
* context lengths
* API endpoints
* API-key requirements
* billing requirements
* privacy/data usage
* expiration dates
* other restrictions

Do not infer limits from testing or observed behavior.

If information cannot be verified, say so or omit it.

## Sources

End every provider file with:

```markdown
**Sources**

- https://...
- https://...
```

Include the most relevant sources used to construct the entry.

Prefer:

1. Official API documentation
2. Official pricing/free-tier documentation
3. Official model documentation
4. Official announcements
5. The three discovery sources
6. Other reputable sources when necessary

Use specific documentation URLs where possible rather than only the provider homepage.

The sources should allow another agent to quickly re-check whether information such as models, rate limits, or free-tier availability has changed.

## Writing style

Be factual, concise, and practical.

Avoid marketing language.

Prefer:

> Provides an OpenAI-compatible API with 20 RPM and 1000 requests/day for models A and B. An account and API key are required. No payment method is required.

over:

> This amazing provider gives developers powerful access to cutting-edge AI models for free!

Focus on information useful to someone who wants to actually use the free API.

## Final verification

Before completing each provider, verify:

* Is the provider still operational?
* Is free API inference actually available?
* Is it available to normal users?
* Is an account required?
* Is an API key required?
* Is payment information required?
* Which models are actually free?
* What are the documented limits?
* Is the API endpoint correct?
* Are the model IDs correct?
* Are important claims supported by sources?
* Does a provider file already exist?
* Is this actually a distinct provider rather than a duplicate/service wrapper?
* For each free model on the provider: does its `models/` card exist, and does the providers table row match the provider file (ID, conditions, limits, verified date)?
* For each model card: is every table row backed by its linked provider file, and are payment-gated rows ⚠-flagged rather than listed as plain free?
* For each model card: is the leaderboard mapping present — `leaderboard_id` + exact integer `leaderboard_rank` when the CSV denotes the model, `leaderboard_rank_estimated: "~N"` (with basis/source/date in the body) when it is a plausible top-level model missing from the snapshot, and neither when it is small, ≥1 year old, superseded, or a specialist (in which case no card should exist at all)?

The final `providers/` directory should be a **clean, deduplicated, independently verified database of genuinely usable free LLM API providers**, not a transcription of the source lists.
