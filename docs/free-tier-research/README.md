Your goal is to find **currently available free LLM API resources** and maintain a clean, accurate provider list.

Your task is to research these discovery sources:

* https://github.com/nejib1/Free-LLM
* https://github.com/CYBIRD-D/FREE-LLM-API-Provider
* https://freellms.org/providers/

Opencode (popular agent harness) also often has for a short time very good models for free via opencode zen, using their api_key "public" , easy extractable via https://raw.githubusercontent.com/anomalyco/opencode/refs/heads/dev/packages/web/src/content/docs/zen.mdx

For every provider you find that offers a **genuinely usable free LLM API**, create or update a Markdown file in:

`providers/<provider-name>.md`

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
4. Prefer official documentation and pricing/free-tier pages.
5. If sources disagree, investigate and use the most recent/reliable information.
6. Do not include providers whose free API access cannot be verified.
7. Do not infer or guess limits.

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
* promotional credits unless clearly useful as a free offering
* free web/chat access with no free API
* models advertised as free but requiring a paid subscription
* services where payment is required to obtain the API access

Clearly distinguish free API access from free application/web access.

## Files

Create one canonical file per provider:

`providers/<provider-name>.md`

Check for an existing file first. If it exists, update it rather than creating a duplicate.

Use stable, human-readable filenames.

Do not create separate files for individual models.

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

The final `providers/` directory should be a **clean, deduplicated, independently verified database of genuinely usable free LLM API providers**, not a transcription of the source lists.
