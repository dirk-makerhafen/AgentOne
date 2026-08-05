# Provider & Model Research

Curated provider and model metadata of **free, flagship-tier models only**.

**Scope:** Top ~10 state-of-the-art models (e.g., GPT-4o, Claude Sonnet 4, Qwen3-235B, Nemotron 3 Ultra, DeepSeek V3, Llama 3.1 405B) — not the long tail of small/quantized/obscure models (e.g., Qwen-8B, Phi-3-mini, dozens of 7B/8B variants).

**Goal:** Maximize value for the user by providing only the best freely usable model APIs — the ones you'd actually pick for production use.

---

### ⚡ QUICK START FOR NEXT AGENT

| Step | Action | Location |
|------|--------|----------|
| 1 | Run all extraction scripts, fix scripts on error  | `python3 scripts/generate_from_*.py --fetch` |
| 2 | Research free models | source websites, web search |
| 3 | Review extracted data, identify best free models | `raw/models/`, `raw/providers/` |
| 4 | **Update curated files** | `models/<slug>.md`, `providers/<slug>.md` |

**Critical:** Scripts write ONLY to `raw/`. Final curated output goes to root `models/` and `providers/` — **manually created**.

## Structure

```
providers/
  README.md
  scripts/                     # extraction scripts (helpers)
  raw/                         # downloaded source data (gitignored) — SCRIPTS WRITE HERE ONLY
      awesome-free-llm-apis.json
      opencode-models-api.json
      awesome-repo-cache/
      free-api-resources-data.py
      hermes-agent-cache/
      models/                  # extracted model cards (for reference during curation)
      providers/               # extracted provider cards (for reference during curation)
  models/                      # CURATED model cards (FINAL OUTPUT — manual creation only)
      <model-slug>.md          # model card with YAML frontmatter
  providers/                   # CURATED provider cards (FINAL OUTPUT — manual creation only)
      <provider-slug>.md       # provider card with YAML frontmatter
```

**KEY: Scripts ONLY read/write to `raw/`. The `models/` and `providers/` directories at the root are for MANUALLY CURATED final output only.**

## Workflow: Two-Part Process

### Part 1: Extract Raw Data (Automated Helpers)

Run extraction scripts to download source data into `raw/` and bootstrap extracted files in `raw/models/` and `raw/providers/`:

```bash
# Source 1: awesome-free-llm-apis data.json (24 free LLM providers)
python3 scripts/generate_from_awesome_apis.py --fetch

# Source 2: opencode test fixtures (120 providers, 2000+ models)
python3 scripts/generate_from_opencode_fixtures.py --fetch

# Source 3: awesome-free-llm-apis skill references (limits, env vars, base URLs)
python3 scripts/generate_from_awesome_repo.py --fetch

# Source 4: free-llm-api-resources MODEL_TO_NAME_MAPPING (human-readable names)
python3 scripts/generate_from_free_api_resources.py --fetch

# Source 5: NousResearch/hermes-agent ProviderProfile (auth, fallback models, aliases)
python3 scripts/generate_from_hermes_agent.py --fetch
```

**Notes:**
- Scripts are **helpers** — they download to `raw/` and write extracted data to `raw/models/` and `raw/providers/`
- **Scripts NEVER write to the root `models/` or `providers/` directories** — those are for manual curation only
- When sources update, scripts may need updates (check source URLs in each script)
- Edit `SKIP_IDS` / `SLUG_OVERRIDES` / `SLUG_MERGE_MAP` in scripts to control inclusion
- Each script is self-contained; no hardcoded provider data

### Part 2: Curate Flagship Models (Ai Driven Research)

After extraction, **research and create the final curated files** in the root `models/` and `providers/` directories:

1. **Review extracted data** in `raw/models/` and `raw/providers/` for reference
2. **Check source websites** (listed in Data Sources below) for new providers/models
3. **Web search** for "best free LLM API 2026", "top free models production ready", etc.
4. **Identify flagship models** — the ~10 models you'd actually use in production
5. **Create/update curated files:**
   - `providers/<slug>.md` — provider info (name, URL, auth, free tier, notes)
   - `models/<slug>.md` — model specs (family, series, vision, reasoning, tool_call, params, context, providers)

**Curation criteria for flagship models:**
- State-of-the-art performance on benchmarks (MMLU, HumanEval, etc.)
- Available free via at least one cloud api provider
- Sufficient context length for production use (≥32K preferred)
- Supports tool calling and/or reasoning
- Actively maintained (not deprecated)

## Regenerate Raw Data

```bash
# Run all extraction scripts in sequence
python3 scripts/generate_from_awesome_apis.py --fetch && \
python3 scripts/generate_from_opencode_fixtures.py --fetch && \
python3 scripts/generate_from_awesome_repo.py --fetch && \
python3 scripts/generate_from_free_api_resources.py --fetch && \
python3 scripts/generate_from_hermes_agent.py --fetch && \
python3 scripts/generate_from_lmsys_arena.py --fetch
```

## Format Reference

### Model card (`models/<slug>.md`)

```yaml
---
name: <slug>                    # colons→dashes, lowercase (e.g., "gpt-4o", "qwen3-235b")
family: <family>                # broad family e.g. gpt, qwen, claude, llama
series: <series>                # model series e.g. gpt-4o, qwen3, sonnet-4
vision: true|false              # supports image input
supports_reasoning: true|false  # supports chain-of-thought / reasoning tokens
supports_tool_call: true|false  # supports function/tool calling
open_weights: true|false        # weights publicly available
self_hosted: true|false         # can be self-hosted
total_parameters: <float>       # billions (e.g., 7.0, 70.0, 235.0)
active_parameters: <float>      # MoE only — active params in billions (e.g., 21.0 for 235B MoE)
context_length: <int>           # max context tokens (e.g., 128000, 1000000)
providers:
  - <provider-slug>             # e.g., "openrouter", "groq", "together"
---
Description...
```

### Provider card (`providers/<provider-slug>.md`)

```yaml
---
name: <display name>            # human-readable (e.g., "OpenRouter", "Groq", "Together AI")
url: "<api base url>"           # e.g., "https://openrouter.ai/api/v1", "https://api.groq.com/openai/v1"
self_hosted: true|false         # provider is a self-hosted platform
free_info:
  api_key_url: "<url>"          # URL to get API key (e.g., "https://console.groq.com/keys")
  setup_instructions: "<text>"  # Step-by-step setup for free tier
  requires_credit_card: true|false  # whether credit card needed for free tier
  free_tier_description: "<text>"   # summary of free tier limits/models
---
Description, auth method (API key / OAuth / none), free tier details, notes.
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
| LMSYS Chatbot Arena | https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset | `scripts/generate_from_lmsys_arena.py` | Model Elo ratings, licenses, orgs — for flagship identification |

### Curated lists (reference-only — markdown, no structured extraction)

These repos are manually curated lists. They contain structured data in markdown tables but no machine-parseable files. They are documented here for awareness and manual cross-reference, but do not have automated extraction scripts.

| Source | URL | Notes |
|--------|-----|-------|
| nejib1/Free-LLM | https://github.com/nejib1/Free-LLM | 45+ providers, self-hosted section, trial credits. Heavy overlap with Sources 1-2. |
| CYBIRD-D/FREE-LLM-API-Provider | https://github.com/CYBIRD-D/FREE-LLM-API-Provider | Chinese platforms (ModelScope, SiliconFlow), NVIDIA full model catalog (129 models). Unique CN coverage. |
| amardeeplakshkar/awesome-free-llm-apis | https://github.com/amardeeplakshkar/awesome-free-llm-apis | Fork of mnfst/awesome-free-llm-apis — already covered by Source 1. |
| ShaikhWarsi/free-ai-tools | https://github.com/ShaikhWarsi/free-ai-tools | Broad scope (IDEs, copilots, RAG). Env variable names for many providers. |
| eudk/awesome-ai-tools | https://github.com/eudk/awesome-ai-tools | Descriptive prose — model lineage, ecosystem overview. No structured data. |
| zebbern/no-cost-ai | https://github.com/zebbern/no-cost-ai | 80+ services, no-signup endpoints, chat interfaces. Includes gray-market/g4f services. |

Data may be out of date or partial — cross-check between multiple sources. When multiple sources provide overlapping metadata for the same provider, scripts use a `SLUG_MERGE_MAP` (or alias-based matching) to merge into the same provider directory, enriching the provider card with info from each source.

## Free Tier Research — Curated Providers

The following table summarizes free tier access details for each curated provider, suitable for populating `free_info` in provider cards.

| Provider | API Key URL | Setup Instructions | Requires Credit Card | Free Tier Description |
|----------|-------------|-------------------|---------------------|----------------------|
| **OpenRouter** | https://openrouter.ai/keys | Sign up with email, go to API Keys page, create key. No credit card. | No | 200 req/day per free model (`:free` suffix). 50+ free models including Nemotron 3 Ultra, Qwen3-235B, DeepSeek V3, GLM-5.2, Gemma 4, GPT-OSS-120B, Kimi K2. Rate limits ~20 req/min. |
| **Groq** | https://console.groq.com/keys | Sign up with email (no card), create API key. | No | All models free (rate-limited). ~30 req/min, ~14,400 req/day. Models: Llama 3.3 70B, Llama 4 Scout/Maverick, Qwen3 32B, GPT-OSS-120B/20B, Gemma 7B/27B, DeepSeek R1 Distill. No credits system. |
| **Google AI Studio** | https://aistudio.google.com/app/apikey | Sign in with Google account, create API key. No credit card. | No | Gemini 2.5 Flash (10 RPM, 250K TPM, 1,500 RPD), 2.5 Flash-Lite (15 RPM, 1,000 RPD), 2.0 Flash (15 RPM, 1,500 RPD), 3 Flash (10 RPM, 1,500 RPD), 3.1 Flash-Lite (15 RPM, 1,000 RPD). All 1M context. Pro models paid-only. Free tier data may be used for model improvement. |
| **Together AI** | https://api.together.ai/settings/api-keys | Sign up with email, get $5 free credits (never expire). | No | $5 free credits on signup. Free tier endpoints for 200+ open models (reduced rate limits vs Turbo). Includes DeepSeek V3, Qwen3-235B, Nemotron 3 Ultra/Super, Llama 3.3 70B, Llama 4 Maverick, GLM-5.2, GPT-OSS-120B. |
| **NVIDIA NIM** | https://build.nvidia.com | Create NVIDIA NGC account (free), generate API key. | No | Free prototyping endpoints for all models on build.nvidia.com. Includes Nemotron 3 Ultra/Super/Nano, Llama-Nemotron. Rate limits suitable for development only. Production requires NVIDIA AI Enterprise. |
| **Cerebras** | https://cloud.cerebras.ai/ | Sign up with email, create API key. No credit card. | No | Free access to select open models: Llama 3.3 70B, Llama 4 Scout/Maverick, Qwen3-235B, GPT-OSS-120B. Ultra-fast inference on wafer-scale hardware. Rate limits not publicly documented. |
| **DeepSeek** | https://platform.deepseek.com/api_keys | Sign up with email, get $5 free credits. | No | $5 free credits on signup. Direct access to DeepSeek V3, R1, V3.1. Competitive per-token pricing after credits. China-based; consider data residency. |
| **Kenari** | https://kenari.id | Sign up with email, create API key. No credit card. | No | Free tier with `:free` suffix models: DeepSeek V4 Flash/Pro, GLM-5.2, GPT-OSS-120B, GPT-5.4-mini, Kimi K2.6, Gemma 4 31B. Indonesian aggregator; latency may vary outside APAC. |
| **UnoRouter** | https://unorouter.com | Sign up with email, create API key. No credit card. | No | 20+ free models with `:free` suffix: GPT-5.5/5.4/5.2, Nemotron 3 Ultra, DeepSeek V4 Flash/Pro, GLM-5.2/4.5-Flash, Gemma 4 31B, Qwen3.5-397B, Kimi K2.6, Minimax M2.7, Step 3.7 Flash. Broadest free catalog among aggregators. |
| **OpenCode Zen** | (Built into opencode) | No setup needed — uses your opencode session. | N/A | Built-in provider for opencode users. 79 models free including: DeepSeek V4 Flash, Nemotron 3 Ultra/Super, GLM-5.2/5/4.7, Kimi K2.6/2.5, Minimax M3, Mimo v2.5, Qwen3.6 Plus, Ring 2.6 1T. Zero config, no separate API key. |

---

**Note:** All providers listed offer genuine free tiers (no credit card required for free access). Rate limits and model availability may change; verify on provider websites before production use.