---
name: Tencent Hunyuan Hy3
developer: Tencent (Hy Team)
canonical_id: tencent/hy3
leaderboard_id: hy3
leaderboard_rank: 51
family: hunyuan
context_window: 256000
reasoning: true
tool_call: true
modalities:
  input: [text]
  output: [text]
open_weights: true
providers:
  - name: Kenari
    file: kenari
    model_id: hy3:free
    conditions: ":free lane billed Rp 0, best-effort; account + key (kn-...), no top-up"
    notes: "Kenari catalogs 262K context (slightly above official 256K max; treat 256K as the cap)"
    verified: "2026-09-05"
  - name: AIHubMix
    file: aihubmix
    model_id: hy3-free
    conditions: "10 trial calls strictly free (account + key, no card); sustained daily quotas after one-time $1+ top-up"
    limits:
      requests:
        minute: 10
        day: 100
    verified: "2026-09-05"
---

Hy3 is Tencent Hy Team's third-generation Hunyuan MoE model (295B total / 21B active, hybrid fast-and-slow-thinking), open-sourced under Apache 2.0 on July 6, 2026 as the successor to the Hy3 preview from late April 2026. It is a strong open-weight reasoning and agentic-coding model that rivals models 2-5× its size.

**Capabilities:**

- Reasoning with fast/slow thinking modes (hybrid MoE), tool/function calling.
- Text in / text out; 256K native context window (official).
- Open weights (Apache 2.0) on Hugging Face (`tencent/Hy3`, BF16) | ModelScope | GitHub | GitCode; production serving via vLLM (`hy_v3` parsers) and SGLang.
- 295B total / 21B active (top-8 of 192 experts), 3.8B MTP layer.

**Providers (free access):**

| Provider | Provider-side ID | Free conditions | Model-specific limits | Verified |
|---|---|---|---|---|
| [Kenari](../providers/kenari.md) | `hy3:free` | `:free` lane billed Rp 0, best-effort; account + key (`kn-...`), no top-up | Per-minute cap plus tiered daily quotas, operator-set (see provider file) | 2026-09-05 |
| [AIHubMix](../providers/aihubmix.md) | `hy3-free` | 10 trial calls strictly free (account + key, no card); sustained daily quotas after one-time $1+ top-up | 100 req/day ∙ 10 req/min shared catalog-wide (see provider file) | 2026-09-05 |

**Notes:**

- Kenari catalogs `hy3:free` at 262K context — slightly above the official 256K max; the official 256K figure is the card default.
- Kilo Code previously listed `tencent/hy3:free` but it was absent from the live catalog on 2026-09-05 (roster rotates) — do not rely on removed IDs.
- AIHubMix sustained daily free quotas require a one-time $1+ top-up (account credit), so sustained use is gated by a minimal payment; 10 trial calls remain card-free, no expiry.

**Sources**

- https://huggingface.co/tencent/Hy3 (official model card: 256K context, MoE 295B/21B, Apache-2.0)
- https://github.com/Tencent-Hunyuan/Hy3 (release notes, serving recipes, open weights)
- https://hy.tencent.com/research/hy3?langVersion=en (official announcement, Hy3 vs Hy3 preview)
- https://www.tencentcloud.com/techpedia/144773 (2026-07-06 release, 256K context, Apache-2.0)
- https://kenari.id/v1/models (live catalog, `hy3:free` verified 2026-09-05)
- https://aihubmix.com/models/free (56-free-lane, `hy3-free` $0/M verified 2026-09-05)