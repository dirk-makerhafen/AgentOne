---
name: Muse Spark 1.2 Contributor
developer: Meta
canonical_id: meta/muse-spark-1-2-contributor
family: muse-spark
leaderboard_id: muse-spark-1.2
context_window: 1048576
max_output_tokens: 943718
reasoning: true
tool_call: true
modalities:
  input: [text, image, video]
  output: [text]
open_weights: false
providers:
  - name: OpenCode Zen
    file: opencode-zen
    model_id: muse-spark-1.2-contributor-free
    conditions: "Anonymous free pool; no account, key, or payment; served ONLY on POST /v1/responses (never chat/completions); limited-time free"
    verified: "2026-09-05"
  - name: Kenari
    file: kenari
    model_id: muse-spark-1-2-contributor:free
    conditions: "`:free` lane billed Rp 0; account + key, no card; live-catalog-verified 2026-09-05 (all `free: true`, no sunset set); per-minute cap + daily quota tiers"
    verified: "2026-09-05"
---

Muse Spark 1.2 Contributor is the discounted contributor tier of Meta's Muse Spark 1.2 reasoning model: the same model at heavily discounted token pricing ($0.10 input / $0.20 output per 1M tokens) in exchange for permission to train future Meta models on prompts and completions. The leaderboard entry for this model is the base model `muse-spark-1.2`; this card covers the contributor tier served free on the providers below. On Opencode Zen the contributor row is served ONLY on `/v1/responses`, never on `/v1/chat/completions`. Sibling tier version: [Muse Spark 1.3 Contributor](muse-spark-1.3-contributor.md).

**Capabilities:**

- Reasoning with selectable effort tiers (`xhigh`, `max`) via a `reasoning_effort` parameter (official announcement).
- Tool/function calling for long-horizon agentic and coding workflows (official model page).
- Text + image + video in / text out; ~1M context (1,048,576 tokens, official model page and pricing docs).
- 943,718 max output (secondary-reported from Meta docs: 90% of the context window).
- Proprietary closed weights — NOT open weights (open-weights release is on Meta's roadmap with no confirmed date).

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [OpenCode Zen](../providers/opencode-zen.md) | `muse-spark-1.2-contributor-free` | Anonymous free pool; no account, key, or payment; limited-time free | None published; free pool enforced via `FreeUsageLimitError` (quota and reset window unknown) | 2026-09-05 |
| [Kenari](../providers/kenari.md) | `muse-spark-1-2-contributor:free` | `:free` lane billed Rp 0; account + key, no card | Per-minute cap per model + daily quota in three tiers; live numbers on kenari.id/plan | 2026-09-05 |

**Notes:**

- `muse-spark-1.2-contributor-free` is absent from Zen's published pricing table — its free status is live-observed only and may be revoked without notice.
- Contributor tier on Meta's own API is paid-but-discounted ($0.10/$0.20 per 1M) with lower rate limits (100 RPM / 3M TPM vs 3000 RPM / 4M Standard); the Zen free pool above is a separate limited-time offering.
- Opencode geo-gates the contributor models by request country — availability may vary by region.
- Knowledge cutoff is not published by Meta — omitted.
- The opencode fixture for Muse Spark 1.1 additionally reports temperature control, structured output, and PDF input (fixture-reported, verify live); omitted from frontmatter as unverified for the 1.2 contributor row.

**Sources**

- https://ai.developer.meta.com/docs/pricing-rate-limits (contributor-tier pricing, rate limits — official)
- https://developer.meta.com/ai/models/muse-spark (model page: 1M context, contributor row — official)
- https://research.meta.ai/blog/multimodal-intelligence-of-muse-spark-1-2 ("ahead of the open-weights release" — currently closed weights, official)
- https://codersera.com/blog/muse-spark-1-3-complete-guide-2026/ (943,718 max output, cutoff unpublished — secondary reporting of Meta docs)
- https://kenari.id/docs/billing (`:free` lane terms)
- raw/opencode-models-api/meta/model_muse-spark-1.1.json (capabilities/context — discovery data, fixture-reported)
