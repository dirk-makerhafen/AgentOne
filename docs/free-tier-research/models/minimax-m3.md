---
name: MiniMax M3
developer: MiniMax
canonical_id: minimax/minimax-m3
family: minimax
context_window: 1000000
reasoning: true
tool_call: true
temperature: true
modalities:
  input: [text, image, video]
  output: [text]
open_weights: true
providers:
  - name: AIHubMix
    file: aihubmix
    model_id: minimax-m3-free
    conditions: "Free-model lane; account + key, no card; trial-use, 429s possible under load"
    verified: "2026-09-05"
---

MiniMax M3 is MiniMax's multimodal long-context model for coding, perception, and agent planning (fixture-reported facts; verify live). Context figures vary by host (512K–1M); paid hosts apply tiered pricing above ~512K context.

**Capabilities:**

- Reasoning, tool/function calling, temperature control (fixture-reported).
- Text + image + video in / text out; up to 1M context (fixture-reported).
- Open weights.

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [AIHubMix](../providers/aihubmix.md) | `minimax-m3-free` | Free-model lane; account + key, no card | None published; free versions are trial-use (limited resources, 429s possible under load) | 2026-09-05 |

**Notes:**

- Fixture-observed (re-verification leads, not in table): $0 `minimax-m3` rows on Kenari, Nvidia NIM, and the opencode-models fixture set — confirm live before use.
- MiniMax's own platform is paid and has no provider file yet; do not confuse fixture $0 rows on paid gateways with standing free tiers.

**Sources**

- https://aihubmix.com/pricing
- raw/opencode-models-api/minimax/model_MiniMax-M3.json (capabilities/context — discovery data)
