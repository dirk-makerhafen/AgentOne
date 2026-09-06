---
name: Qwen3.6-35B-A3B
developer: Alibaba (Qwen team)
canonical_id: qwen/qwen3.6-35b-a3b
leaderboard_id: qwen3.6-35b-a3b
leaderboard_rank: 96
family: qwen3
context_window: 262144
modalities:
  input: [text, image]
  output: [text]
providers:
  - name: InferX
    file: inferx
    model_id: Qwen3.6-35B-A3B-FP8
    conditions: "InferX Free $0/mo promo ('Free · 100% off'); account + key; promos rotate, re-verify pricing page"
    verified: "2026-09-05"
  - name: Hetzner Inference API
    file: hetzner-inference
    model_id: Qwen/Qwen3.6-35B-A3B-FP8
    conditions: "Free while experimental; Hetzner customer account + token, no billing"
    verified: "2026-09-05"
---

Qwen3.6-35B-A3B is the MoE sibling of Alibaba Qwen team's April 2026 Qwen3.6 generation: a 35B-total / 3B-active Mixture-of-Experts model served as FP8 rows on InferX and Hetzner. Its 27B dense sibling has its own [card](qwen3.6-27b.md). Qwen3.8 (August 2026) is a separate, newer generation with its own [card](qwen3.8.md).

**Capabilities:**

- Text + image in / text out (Hetzner documents vision input for this row).
- 262,144 context (**provider-reported** — InferX/Hetzner catalog figures, not an official weights spec; verify live).

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [InferX](../providers/inferx.md) | `Qwen3.6-35B-A3B-FP8` | InferX Free $0/mo promo; account + key | No published numbers; promos rotate | 2026-09-05 |
| [Hetzner Inference API](../providers/hetzner-inference.md) | `Qwen/Qwen3.6-35B-A3B-FP8` | Free while experimental; Hetzner customer account + token, no billing | None published combo-specific; provider-wide per-key caps apply (see provider file); roster changes | 2026-09-05 |

**Notes:**

- Context figure is provider-reported (InferX lists 262,000; Hetzner lists 262,144 tokens), not an official model-card spec — card default uses 262,144 pending official confirmation.
- Sibling size: [`Qwen3.6-27B`](qwen3.6-27b.md) (27B dense flagship; thinking/non-thinking modes and tool calling documented there).
- Thinking/tool-call behavior and weight licensing are documented for the 27B sibling — not separately verified for this FP8 endpoint; verify live before relying on them.
- Do not confuse with `Qwen3-32B` ([card](qwen3-32b.md)) or `Qwen3.5-397B-A17B` ([card](qwen3.5-397b.md)).

**Sources**

- https://inferx.net/pricing/endpoints
- https://docs.hetzner.com/general/company-and-policy/experiments/inference/
