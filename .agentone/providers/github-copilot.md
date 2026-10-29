---
name: GitHub Copilot
url: "https://github.com/features/copilot"
api_base: "https://api.githubcopilot.com"
setup_instructions: |
  1. Have an active GitHub Copilot subscription (individual, business, or enterprise).
  2. Use the GitHub Copilot CLI or VS Code extension which automatically handles authentication.
  3. For direct API access, use the GitHub token from the Copilot extension (stored in keychain/credential manager).
  4. Call the OpenAI-compatible endpoint at https://api.githubcopilot.com with the token as Bearer token.
api_key_url: "https://github.com/settings/copilot"
limits:
  requests:
    minute: 300
    day: 10000
---

GitHub Copilot provides API access to 37 models (25 free with subscription, 12 paid). Free models available to all Copilot subscribers at no additional cost.

**Free Tier (with active Copilot subscription):**

- 25 models free with Copilot subscription (individual $10/mo, business $19/mo/user, enterprise $39/mo/user).
- 300 RPM, 10,000 RPD (estimated; not publicly documented).
- No additional per-token charges for free models.

**Free Models (verified 2026-10-27 from opencode fixtures):**

### OpenAI GPT Models
- `gpt-5` — 128K context, reasoning, tool calls
- `gpt-5.1` — 264K context, reasoning, tool calls
- `gpt-5.1-codex` — 400K context, reasoning, tool calls
- `gpt-5.1-codex-mini` — 400K context, reasoning, tool calls
- `gpt-5.1-codex-max` — 400K context, reasoning, tool calls
- `gpt-5.2` — 264K context, reasoning, tool calls
- `gpt-5.2-codex` — 400K context, reasoning, tool calls
- `gpt-5.3-codex` — 400K context, reasoning, tool calls
- `gpt-5.4` — 400K context, reasoning, tool calls
- `gpt-5.4-mini` — 400K context, reasoning, tool calls
- `gpt-5-mini` — 264K context, reasoning, tool calls
- `gpt-4.1` — 128K context, tool calls
- `gpt-4o` — 128K context, vision, tool calls

### Anthropic Claude Models
- `claude-sonnet-4` — 216K context, reasoning, tool calls, vision
- `claude-sonnet-4.5` — 144K context, reasoning, tool calls, vision
- `claude-sonnet-4.6` — 200K context, reasoning, tool calls, vision
- `claude-opus-4.5` — 160K context, reasoning, tool calls, vision
- `claude-opus-4.6` — 144K context, reasoning, tool calls, vision
- `claude-opus-41` — 80K context, reasoning
- `claude-haiku-4.5` — 144K context, reasoning, tool calls, vision

### Google Gemini Models
- `gemini-2.5-pro` — 128K context, tool calls
- `gemini-3-flash-preview` — 128K context, reasoning, tool calls
- `gemini-3-pro-preview` — 128K context, reasoning, tool calls
- `gemini-3.1-pro-preview` — 128K context, reasoning, tool calls

### xAI Grok Models
- `grok-code-fast-1` — 128K context, reasoning, tool calls

**Paid Models (additional charges apply):**
- `claude-sonnet-5`, `claude-opus-4.7`, `claude-opus-4.8`, `claude-fable-5`
- `gemini-3.5-flash`, `gpt-5.5`, `gpt-5.6-*` variants, `mai-code-1-flash-picker`, `kimi-k2.7-code`

**Limits:**

- 300 RPM, 10,000 RPD (estimated; GitHub doesn't publish exact limits).
- Rate limits enforced per Copilot subscription.
- Free models: $0 input/output tokens.
- Paid models: standard per-token pricing (e.g., Claude Sonnet 5: $2/$10 per 1M).

**Notes:**

- Active GitHub Copilot subscription required; no separate API key (uses Copilot auth).
- OpenAI-compatible: `https://api.githubcopilot.com`.
- Model IDs use simple names (no provider prefix for most).
- Free model access tied to subscription tier; enterprise gets highest limits.
- VS Code extension and GitHub Copilot CLI are primary interfaces; direct API use is secondary.

**Sources**

- https://github.com/features/copilot (official site)
- https://docs.github.com/en/copilot (documentation)
- https://api.githubcopilot.com/models (live model list, auth required)
- docs/free-tier-research/raw/opencode-models-api/github-copilot/ (37 model fixtures, 25 free, verified 2026-10-27)