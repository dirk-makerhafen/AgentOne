# Provider/model catalog generation

The upstream discovery data is downloaded and normalized by code rather than
by research scripts. The code lives in `registry/catalog/` (next to
`registry/sources/` and `registry/loader/`), because it produces canonical
`.agentone/` data for the same registry pipeline. `.agentone/scripts/` is only
for agent-callable UI tools, and `docs/` is documentation only.

The opencode models fixture is the **base set**: the providers and models it
lists decide which cards exist. The two free-LLM catalogs are a **second pass**
that only adds providers and models opencode misses; they never overwrite an
opencode record.

## Run it

```bash
venv/bin/python manage.py refresh_catalog                 # download + rebuild base dataset
venv/bin/python manage.py refresh_catalog --offline       # rebuild from cache
venv/bin/python manage.py refresh_catalog --dry-run       # report changes only

venv/bin/python manage.py refresh_free                    # extract free-offering candidates
venv/bin/python manage.py refresh_free --offline          # reuse cached provider /models payloads
venv/bin/python manage.py refresh_free --skip-model-lists # ignore provider /models discovery

venv/bin/python manage.py merge_free_reviews --root .agentone  # write reviewed .agentone/free/
```

Options: `--root` (manifest root, default `agentone_root()`), `--cache-dir`
(raw upstream payloads), `--candidates-dir` (generated leads), `--no-prune`.

Raw payloads are cached in `~/.agentone/var/cache/provider-catalog/` and
generated leads plus curated reviews in `~/.agentone/var/cache/free-tier/`
(re-creatable state, see [folders.md](folders.md)). The cache manifest records the URL, fetch
time and status of each source; a failed download leaves the last cached
payload in place and is reported as a warning. The FreeLLMAPI feed is signature
-verified and must remain the public `monthly` tier.

Sources:

| Source | Payload | Used for |
|---|---|---|
| `opencode-models-api` | `<provider>.models` fixture | base set of providers/models; richest metadata (dates, reasoning options, cost, capabilities) |
| `freellmapi-catalog` | `platforms[]`, `models[]`, `quirks[]` | only providers/models opencode misses; quotas, ranks, quirks |
| `awesome-free-llm-apis` | `providers[]` | only providers/models the earlier passes miss; provider URL/description, free-tier roster |

## Output layout

```
.agentone/
├── providers/
│   ├── <provider>.md                    # existing curated research (unchanged)
│   └── <provider>/
│       ├── <provider>.json              # provider identity
│       └── <model>.json                 # provider-local model record
├── models/
│   └── <model>.md                       # existing curated research (unchanged)
└── free/                                # final reviewed free dataset (versioned)
    ├── index.json                       # reviewed counts + provider index
    └── <provider>.json                  # candidates with verdict/conditions

~/.agentone/var/cache/free-tier/         # dev inputs (re-creatable, not versioned)
├── candidates/
│   ├── index.json                       # source/count/provider index
│   └── <provider>.json                  # one provider's free-offering leads
└── reviews/
    └── <provider>.json                  # curated agent verdicts
```

There is no generated global `models/*.json` folder. Models live next to the
provider that offers them, mirroring opencode's layout. Every generated file
has `"_generated_by": "registry.catalog"`. Pruning is marker-based: only
generated JSON that is no longer produced by the sources is deleted; markdown
cards, hand-written JSON and empty-but-manual directories are left alone.
Legacy generated `models/*.json` files are removed; provider directories are
removed once empty.

Writes are atomic and byte-stable (`sort_keys=True`, UTF-8, trailing newline),
so repeated runs produce identical files.

### Provider record

`providers/<slug>/<slug>.json` carries the merged identity: `slug`, `name`,
`api_base`, `api_base_source` (when promoted/filled), `url`, `doc`, `env`,
`npm`, `description`, `catalog_version`, provider `quirks`, `model_count`,
plus `aliases` and `sources` provenance.

### Model record

`providers/<provider>/<model>.json` is the model record for that provider:
`provider`, `model`/`slug`, `name`, `canonical_id`, `family`, `developer`,
`release_date`, `last_updated`, `knowledge_cutoff`, `reasoning`,
`reasoning_options`, `tool_call`, `interleaved`, `structured_output`,
`temperature`, `modalities`, `open_weights`, `context_window`,
`max_output_tokens`, `cost`, `status`, `provider_model_id` (plus all
`provider_model_ids` seen upstream), catalog ranks/quotas/limits, `variants`
(collapsed slugs), `aliases` and `sources`.

The same model may have a record under several providers: opencode's curated
set stays authoritative for each of those providers, and free-catalog data is
only added where opencode has no record.

## Normalization

Model IDs are lowercased, namespaced IDs are reduced to their final segment
(`openai/gpt-oss-120b`, `@cf/meta/llama-3.2-1b`, `accounts/.../models/...`),
region/vendor prefixes are removed, separators are unified and access suffixes
(`:free`, `-free`, `-preview`, `-beta`, `-latest`, `-experimental`) are dropped.
Known org prefixes written with a dash instead of a slash (`zai-org-`, `z-ai-`,
`zai-`, `moonshot-`) are stripped the same way, so `zai-org-glm-4.6` and
`zai-org/glm-4.6` both become `glm-4-6`. Hyphenated org namespaces joined with
a dot (`aion-labs.aion-2-0`) are stripped too; version dots (`claude-3.5`,
`dots.ocr`) are left alone. Dots before version numbers become
dashes (`GLM-5.3` → `glm-5-3`). All raw IDs
remain in `aliases`, so nothing is unrecoverable. See
`registry/catalog/normalize.py` for the exact rules and the explicit provider
alias table.

When sources disagree, a fixed priority decides the stored value:
`opencode-models-api` → `freellmapi-catalog` → `awesome-free-llm-apis`.
The merge never guesses: absent values stay absent.

### Version consolidation

Upstream feeds publish the same model repeatedly as dated builds, `vN` variants,
build/deployment suffixes and vendor-prefixed IDs. Before writing files,
`registry/catalog/versions.py` groups those IDs **within each provider** by their
clean base and keeps the newest dated variant as that provider's model record:

| Variants | Canonical card |
|---|---|
| `claude-3-5-sonnet-20240620`, `claude-3-5-sonnet-20241022`, `claude-3-5-sonnet-v2`, `anthropic-claude-3-5-sonnet` | `claude-3-5-sonnet.json` |
| `devstral-small-2505`, `devstral-small-2507`, `devstral-small-2512` | `devstral-small.json` |
| `qwen3-235b`, `qwen3-235b-a22b-instruct-2507`, `qwen3-235b-a22b-thinking-2507`, `qwen3-235b-a22b-fp8`, `qwen3-235b-a22b-instruct-2507-tee` | `qwen3-235b-a22b.json` |

The parser strips trailing dates in `YYYYMMDD`, `YYMMDD`, `YYYYMM`, `YYMM`,
`MMDD`, `MM-DD` and `MM-YYYY` forms, using the record's `release_date` /
`last_updated` to disambiguate `MMDD` from `YYMM`. It then strips an explicit
allowlist of build/mode/deployment tokens (`instruct`, `thinking`, `reasoning`,
`fp8`, `turbo`, `tee`, `tput`, `maas`, ...), plus `vN` and context-size suffixes.
Product tiers that are genuinely different models (`flash`, `pro`, `lite`,
`mini`, `coder`, ...) are deliberately not stripped. A tiny
`MODEL_BASE_ALIASES` table handles known abbreviations such as
`qwen3-235b` → `qwen3-235b-a22b`.

The newest variant supplies the fields; the older slugs are kept in `variants`
and all raw IDs remain in `aliases`. The winning variant's `provider_model_id`
stays primary, and every raw ID used by that provider is retained in
`provider_model_ids`. An exact-base `canonical_id` is preferred when one exists.

### Date cutoff

Models whose newest known `release_date` / `last_updated` year is before 2025
are dropped together with their offerings; providers left with no offerings are
dropped too. Undated models are kept (missing data is not evidence of age), and
a pre-2025 release with a 2025+ update stays. The cutoff is
`MODEL_CUTOFF_YEAR` in `registry/catalog/build.py`.

### Usable-API filter

AgentOne can only use a provider it can call, so providers without a single API
URL are not written. A provider is kept when it has a top-level `api_base`
(`api` from opencode, `baseUrl` from the awesome feed), when its `npm` runtime
has a pinned public SDK default (`registry/catalog/normalize.py` →
`SDK_DEFAULT_API_BASES`), or when all of its offerings share one model-level
endpoint. The latter two are promoted to `api_base` and tagged with
`api_base_source` (`sdk-default` / `offering-endpoint`). With the current feeds
this restores 11 opencode providers that omit `api` but ship a fixed default,
including Anthropic (`@ai-sdk/anthropic` → `https://api.anthropic.com/v1`).
Packages that need account/project-specific URLs (Azure, Bedrock, Vertex, SAP,
...) have no pinned default and remain dropped, as do providers with conflicting
per-model endpoints (for example `azure-cognitive-services`) and models left
with no provider.

After opencode base selection, free-catalog additions, version consolidation,
the date cutoff and the API filter the dataset is **101 providers and 2,717
model records** (2,818 JSON files). All base-catalog providers have a non-empty
`api_base`; the two account-scoped free-created gateways are the only exception
(and Cloudflare is explicitly out of scope for now).

Every generated provider and model file also carries `catalog_updated_at`, a UTC
ISO-8601 timestamp of the last generation pass that actually changed that
record. It is distinct from a model's upstream `last_updated` (release/update
date). Unchanged files keep their previous stamp, so rerunning either command
does not rewrite the dataset or churn timestamps.

## Free-offering extraction (part 1)

`registry/catalog/free.py` + `venv/bin/python manage.py refresh_free` write a
deterministic set of files under
`~/.agentone/var/cache/free-tier/candidates/`: a small `index.json` plus one
`<provider>.json` per provider. It is **extraction only**: no `free` verdict
and no `conditions` are derived. Part 2 (agent-driven verification) consumes
these files provider by provider; part 3 tests the result.

Sources used:

- `opencode-live-models` — the live `/v1/models` response. Models with an
  explicit `-free`/`:free`/`/free` marker or an all-zero cost are extracted,
  together with capabilities, limits and API base URLs.
- `opencode-models-api` — the curated fixture; the same free markers and
  zero-cost rule apply.
- `freellmapi-catalog` — the signed public **monthly** feed. Every model is a
  lead; `limits`, `monthlyTokenBudget`, ranks, `enabled`, vision/tool hints and
  resolved quirks are preserved. The structured `limits` object is normalized by
  dropping nulls, and `monthlyTokenBudget` is parsed for additional numeric
  quotas.
- `awesome-free-llm-apis` — every listed model is a lead; provider description,
  `rateLimit`, context/max-output labels and modality notes are preserved. The
  free-text `rateLimit` is also parsed into numeric quotas.
- `provider-models-api` — a best-effort `GET {api_base}/models` pass over the
  generated providers. Payloads are cached under
  `~/.agentone/var/cache/provider-catalog/model-lists/` with a manifest; only
  IDs carrying a free marker are added. Auth failures are recorded, not fatal,
  and `--offline` replays the cache.

The free files are deliberately thin. Each provider document carries the
generation marker, `provider`, `schema_version`, `sources`, `name`, provider-level
`signals` and `candidate_count` once. Each candidate carries only `model`
(canonical slug), `model_name`, `provider_model_id` (the exact string to send as
`model` in an API call) and optional free-tier `limits`. The matching model file
is always `providers/<provider>/<model>.json`; per-candidate `provider`,
`model_file`, `signals`, `source_names`, `slug` and other evidence are no longer
repeated there. Model-level data is moved into that regular model file (except
free-tier `limits`, which stay on the candidate). If it does not exist
it is created with `generated_from: "free-candidates"`; if it already exists the
canonical values win and any genuinely new evidence is stored under
`candidate_evidence` (`facts`, `raw`, `sources`, IDs, variants, API bases). When
several leads resolve to the same raw model ID, they are merged into one model
file instead of creating near-duplicates. The main `refresh_catalog` pass
preserves that nested evidence, so the two commands are idempotent in either
order. Every file is byte-stable and overwritten atomically; stale generated
files (including the old single `candidates.json`) are pruned, while
hand-written JSON is never clobbered.

Quota parsing lives in `registry/catalog/normalize.py` and is shared by the base
and free builders. It handles compact units (`20 RPM`, `500K TPM`), word units
(`200 req/hr`, `1,000 requests/month`, `20k tok/day`, `1 concurrent request`),
scales (`K`/`M`/`B`) and qualifiers (`/model`, `per IP`, `/account`). The
canonical keys are `rps`/`rpm`/`rph`/`rpd`, `tps`/`tpm`/`tph`/`tpd`, plus
`requests_per_month`, `tokens_per_month`, `concurrency` and qualified variants
such as `rpd_model` / `rpm_ip`. A leading `~` is ignored and treated as an
exact value. Structured FreeLLMAPI `limits` win over values parsed from labels.
Currency budgets (`$0.25/week`), credit labels, ranges, non-request units and
qualitative text are deliberately **not** parsed; the original label remains in
`rate_limit_label` / `quota_label` and the full payload in `raw`. Numeric
quotas belong to the free offering, not the model: they are written only to the
`limits` field of the matching cached `candidates/<provider>.json` candidate and
are never stored on provider/model JSON files.

API bases are filled from three local sources before writing: the base provider
record (`catalog-provider`), the curated `.agentone/providers/*.md` research
cards (`curated-provider-cards`), and a small table of documented static bases
in `registry/catalog/cards.py` (`provider-docs`, each entry carrying its source
URL). Account-specific gateways such as Cloudflare AI Gateway and GitLab Duo
have no reusable base and are deliberately left without one.

A small set of provider fields is agent-curated and preserved across both
writers: `description`, `setup_instructions`, `url`, `api_key_url`,
`default_api_key`, `doc`, `litellm_prefix`, `wire` and `research_sources`. The
task files in `docs/free-tier-verification/` fill these in place on
`.agentone/providers/<provider>/<provider>.json`; all generated fields are
rewritten normally.

With the current cached sources this produces **84 candidate files plus
`index.json`** in the free-tier cache, covering **815 candidates**, and creates
**382 new model files** plus **32 minimal provider files** for offerings that
were not in the base catalog.

## Scope / next step

The base catalog and free-candidate extraction only gather data. They do
**not** decide what is free: raw costs, quota labels, limits and
`premium_since` are stored as reported, but no `free` or `conditions` field is
derived. That verdict needs the agent-driven verification pass (part 2) and
then testing (part 3).

Copy/paste task files for those passes are in
[`docs/free-tier-verification/`](free-tier-verification/README.md).
`02-provider-metadata.md` enriches allowlisted curated fields on provider JSON
files; `03-verify-free-tier.md` writes free-tier verdicts to
`~/.agentone/var/cache/free-tier/reviews/<provider>.json`. Neither task edits
generated model files or the reviewed dataset in `.agentone/free/`.

The curated reviews are merged by a deterministic, human-run command:

```bash
venv/bin/python manage.py merge_free_reviews --root .agentone
```

It validates every cached review file and writes the final `.agentone/free/`
dataset from `candidates/` plus `reviews/` in the free-tier cache. Errors block
writing; warnings (unreviewed candidates, unknown keys, stale dates) are
reported and can be promoted with `--strict`. `--dry-run` validates without
writing. The dataset is rebuilt from scratch, so a deleted review removes its
verdict on the next run. It never touches the database. `refresh_free` only
refreshes the cached candidates; it never overwrites the reviewed dataset.

`reload_all` loads the generated JSON dataset into the database through
`registry/loader/load_providers_json.py`. It reads each
`.agentone/providers/<provider>/<provider>.json` provider record and the
`<model>.json` records beside it, merges the candidates/verdicts from
`.agentone/free/`, and upserts `ApiProvider`, `AiModel` and `AiModelOffering`
rows. Exact `leaderboard_rank` integers and `leaderboard_rank_estimated: "~N"`
strings both land in the sortable `AiModel.leaderboard_rank` integer, with
`leaderboard_rank_is_estimate` set for the latter. The legacy markdown loader
remains as a fallback for installations that still carry `*.md` research cards.

Free offerings come from several signals, strongest first: a reviewed `free`
verdict (with its conditions and verification date), a `rejected` /
`payment_gated` verdict (clears the flag), then the model record's explicit
`isFree` flag, zero prompt/completion pricing or a `:free` model-id lane. Bare
candidates with no evidence leave any previously curated free state untouched,
so a reload never silently drops verified free tiers that have not been
re-reviewed yet.

## Model leaderboard ranks

`venv/bin/python manage.py sync_model_ranks --root .agentone` downloads the
current LMArena ratings and ZeroEval benchmark scores, folds in the legacy
snapshot so older models keep a rank, and rebuilds a deterministic
`leaderboard.csv` under `~/.agentone/var/cache/free-tier/leaderboard/`. It maps
leaderboard IDs onto canonical model slugs (exact, normalized, then provider
aliases) and writes `leaderboard_id` plus `leaderboard_rank` onto every provider
record for a matched model. Rank fields are curated overlays: catalog regeneration
preserves them.

Not every catalog model has a leaderboard entry, so the command also writes the
tracked, editable table [`docs/model-ranks.md`](model-ranks.md). It has one row
per canonical model (941 today), sorted by model name with vendor prefixes and
provider annotations ignored, and an empty `rank` cell where no leaderboard
entry was found. An agent can research those gaps and
fill in an exact rank or an estimate such as `~120`, then:

```bash
venv/bin/python manage.py sync_model_ranks --root .agentone --import
```

imports only the filled cells back into the model JSON files. Filled cells are
also preserved by later refreshes; blank cells are re-derived from the live
leaderboard. `--offline` reuses cached data, `--export` regenerates the table
from ranks currently in the model files, and `--dry-run` reports without writing.
The ZeroEval token comes from `$ZEROEVAL_API_KEY`, falling back to the legacy
`docs/free-tier-research/scripts/secret_api_keys` file.
