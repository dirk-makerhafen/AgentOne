---
name: Dots-3-Note Preview
developer: Dots Studio
canonical_id: dots-studio/dots-3-note-preview
leaderboard_rank_estimated: ~48
family: dots
context_window: 512000
reasoning: true
tool_call: true
modalities:
  input:
  - text
  - image
  - video
  - audio
  output:
  - text
open_weights: true
---

Dots-3-Note Preview is an open-weights multimodal Mixture-of-Experts model from Dots Studio (the AI lab at Xiaohongshu / RedNote; earlier dots.llm and dots.ocr releases used the rednote-hilab name): 280B total parameters with 16B active, released Aug 14 2026 under Apache 2.0. It is the lightest model in the Dots 3 family, optimized for reasoning, agents, and multimodal perception.

**Capabilities:**

- Multimodal input (text, image, video, audio) with text output (official GitHub repo spec table; inputs projected per official serving recipes).
- Reasoning and agent workflows: personal-assistant agents, coding and computer use, deep information retrieval (official tech blog; Claw-Eval, SWE-bench-pro, BrowseComp, ARC-AGI-2 benchmark tracks).
- Tool/function calling (catalog-reported, consistent across catalogs).
- 512,000-token context window (official router pages); the official SGLang serving recipe uses a 524,288 context length.
- Open weights under Apache 2.0 (official Hugging Face repos `dots-studio/dots3-note-prev` and `-fp8`, plus ModelScope; BF16 and FP8 checkpoints).

**Notes:**

- Developer attribution: the model org is `dots-studio` on Hugging Face / ModelScope and `studio-dots-ai` on GitHub, with contact at a xiaohongshu.com address; third-party catalogs describe it as "the AI lab at Xiaohongshu (RedNote), also behind the dots.llm and dots.ocr models released under the rednote-hilab name". Use `dots-studio` as the canonical vendor prefix.
- No `limits` in frontmatter: no combo-specific numerics are documented for any of the rows; provider-wide defaults stay in the provider files (ZenMux row recorded at 393,100 context per its live model entry, vs 512K card default).
- Max output tokens: catalogs disagree (512K vs ~460.8K/461K) — omitted.
- Temperature / structured output / top_p: catalog-reported only, not verified against official sources — omitted.
- Knowledge cutoff is unpublished — omitted.
- `leaderboard_rank_estimated: "~48"` (2026-09-05): no `leaderboard.csv` entry (released Aug 14 2026; absent from the 2026-09-06 CSV refresh). Basis: official benchmark table shows it matching/beating Hy3 (CSV rank 51) on headline axes — SWE-bench Verified 78.4 vs 78.0, Terminal-Bench 2.1 75.1 vs 71.7, ARC-AGI-2 81.4 vs 35.8, Codeforces 3056. Company-reported table, so directional; independent ModelCap composite estimate is lower (~147). Estimate sits just above Hy3.

**Sources**

- https://huggingface.co/dots-studio/dots3-note-prev (official model repo: Apache 2.0, "developed and released by dots studio", OpenRouter free link)
- https://github.com/studio-dots-ai/dots3-note-prev (official repo: input text/image/video/audio, output text, license, xiaohongshu.com contact)
- https://studio.dots.ai/dots/dots3-en.html (official tech blog: reasoning/agent/multimodal positioning)
- https://openrouter.ai/dots-studio/dots-3-note-preview:free (512K context, 16B-active/280B MoE, free variant)
- https://developer.puter.com/ai/dots-studio/dots-3-note-preview/ (catalog: Dots Studio/Xiaohongshu attribution, 512K context — catalog-reported)
- https://api.kilo.ai/api/gateway/models (live catalog `:free` row, 512000 context — free-route figure)
- https://unorouter.com/en/models (live free catalog — re-verification lead for the no-prefix ID)
- https://aihubmix.com/models/free (live `-free` catalog — re-verification lead for the `-free` ID)
