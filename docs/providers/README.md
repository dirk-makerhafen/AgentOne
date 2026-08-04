# Provider & Model Research

Curated provider and model metadata of free, state-of-the-art models. 
Contains only the latest, greatest and best available models, not the mass of small or old free models. 
Goal is to maximise value for the user by providing a list of the best availabe and freely usable ai. 


## Structure

```
providers/
  README.md
  scripts/                     # reusable scripts for auto-extracting data
  models/                      # free, sota models.
      model_name.md            # 
  provider/
      provider_name.md         # provider name, URL, description
```

## Quick Start

To add/update providers from structured data feeds:

```bash
# Source 1: awesome-free-llm-apis data.json (24 free LLM providers)
python3 scripts/generate_from_awesome_apis.py --fetch

# Source 2: opencode test fixtures (120 providers, 2000+ models)
python3 scripts/generate_from_opencode_fixtures.py --fetch

# Source 3: awesome-free-llm-apis skill references (docs, limits, env vars)
python3 scripts/generate_from_awesome_repo.py --fetch

# Source 4: free-llm-api-resources MODEL_TO_NAME_MAPPING (model name enrichment)
python3 scripts/generate_from_free_api_resources.py --fetch

# Source 5: NousResearch/hermes-agent ProviderProfile (env vars, base URLs, fallback models)
python3 scripts/generate_from_hermes_agent.py --fetch
```

Edit the `SKIP_IDS` set or `SLUG_OVERRIDES` dict in each script to control which providers are included. Scripts create provider dirs, `models.md`, and model cards, and update existing cards when a provider is newly added. Each script is self-contained and fetches its own data from its source URL — no hardcoded provider data.

## Format Reference

### Model card (`models/<slug>.md`)

```yaml
---
name: <slug>                    # colons→dashes, lowercase
family: <family>                # broad family e.g. gpt, qwen, claude
series: <series>                # model series e.g. gpt-4o, qwen3, sonnet
vision: true|false
supports_reasoning: true|false
supports_tool_call: true|false
open_weights: true|false
self_hosted: true|false
total_parameters: <float>      # billions
active_parameters: <float>     # MoE only
context_length: <int>
providers:
  - <provider-slug>
---
Description...
```

### Provider card (`<provider>/provider.md`)

```yaml
---
name: <display name>
url: "<api base url>"
self_hosted: true|false
---
Description, auth method, notes.
```


## Data Sources

### Extraction scripts (machine-parseable, actively maintained)

| Source | URL | Script | Data |
|--------|-----|--------|------|
| awesome-free-llm-apis (JSON) | https://raw.githubusercontent.com/mnfst/awesome-free-llm-apis/refs/heads/main/data.json | `scripts/generate_from_awesome_apis.py` | Provider names, models, context, modalities |
| opencode test fixtures (JSON) | https://raw.githubusercontent.com/anomalyco/opencode/refs/heads/dev/packages/opencode/test/tool/fixtures/models-api.json | `scripts/generate_from_opencode_fixtures.py` | Provider names, models, env vars, capabilities |
| awesome-free-llm-apis (repo) | https://github.com/mnfst/awesome-free-llm-apis/tree/main | `scripts/generate_from_awesome_repo.py` | Limits, base URLs, env vars, model lists |
| free-llm-api-resources | https://github.com/cheahjs/free-llm-api-resources/tree/main | `scripts/generate_from_free_api_resources.py` | Human-readable model names per model ID |
| NousResearch/hermes-agent | https://github.com/NousResearch/hermes-agent/tree/main/plugins/model-providers | `scripts/generate_from_hermes_agent.py` | Env vars, base URLs, fallback models, auth types, aliases |

### Curated lists (reference-only — markdown, no structured extraction)

These repos are manually curated lists. They contain structured data in markdown
tables but no machine-parseable files. They are documented here for awareness and
manual cross-reference, but do not have automated extraction scripts.

| Source | URL | Notes |
|--------|-----|-------|
| nejib1/Free-LLM | https://github.com/nejib1/Free-LLM | 45+ providers, self-hosted section, trial credits. Heavy overlap with Sources 1-2. |
| CYBIRD-D/FREE-LLM-API-Provider | https://github.com/CYBIRD-D/FREE-LLM-API-Provider | Chinese platforms (ModelScope, SiliconFlow), NVIDIA full model catalog (129 models). Unique CN coverage. |
| amardeeplakshkar/awesome-free-llm-apis | https://github.com/amardeeplakshkar/awesome-free-llm-apis | Fork of mnfst/awesome-free-llm-apis — already covered by Source 1. |
| ShaikhWarsi/free-ai-tools | https://github.com/ShaikhWarsi/free-ai-tools | Broad scope (IDEs, copilots, RAG). Env variable names for many providers. |
| eudk/awesome-ai-tools | https://github.com/eudk/awesome-ai-tools | Descriptive prose — model lineage, ecosystem overview. No structured data. |
| zebbern/no-cost-ai | https://github.com/zebbern/no-cost-ai | 80+ services, no-signup endpoints, chat interfaces. Includes gray-market/g4f services. |

Data may be out of date or partial — cross-check between multiple sources. When
multiple sources provide overlapping metadata for the same provider, scripts use
a `SLUG_MERGE_MAP` (or alias-based matching) to merge into the same provider
directory, enriching `provider.md` with info from each source.