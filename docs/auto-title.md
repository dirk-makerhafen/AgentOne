# Automatic chat titles

AgentOne gives a new user-started chat a short, descriptive name from its first
user message. The title is generated **in a forked copy of the same session**
and written back to the parent, using the same fork/auto-await pattern as
compaction and reflection.

## What other harnesses do

| Harness | How it names a new chat | Notable detail |
|---|---|---|
| Claude Code | Background Haiku call generates a title from the first message | Keeps a separate `ai-title` and `custom-title`; an explicit rename wins over the generated one. |
| OpenCode | Hidden `title` agent / `SessionTitle.generate` | Runs outside the user-visible agent, so it does not pollute the conversation. |
| Codex ACP | Ephemeral thread with a cheap model, expects JSON `{"title": ...}` | Has an explicit-rename guard so a later user rename is not overwritten. |
| Cursor | Dedicated `NameAgent` | Same idea: a small auxiliary agent whose only job is naming. |
| Codex CLI | Local title generation capped at 36 characters | Short, terminal-friendly labels. |
| pi | No built-in auto-naming | Title is supplied manually. |

Common pattern: **generate out-of-band, keep the generated name separate from
the user's own name, and never let the generator overwrite an explicit
rename.** AgentOne follows that pattern, but reuses the forked session instead
of paying for a fresh cold prompt.

## AgentOne design

### Trigger

`.agentone/scripts/core/ingest_user_message.py` checks, after the first
`Message` has been persisted, whether:

- auto-titling is enabled (`AGENTONE_AUTO_TITLE_ENABLED`),
- this is a root user chat (`SessionType.SESSION`, no `parent_session`),
- `SessionModel.name_is_auto` is still `True`,
- the message is a `USER_CHAT`,
- there was no earlier `USER_CHAT` in the session.

`turn_count` cannot be used because it is reset on every inbound message; the
message chain is the reliable signal. The trigger is worker-side, after
persistence, so the first message is guaranteed to exist for the fork to
anchor to.

Short greetings and acknowledgements (under `AGENTONE_AUTO_TITLE_MIN_CHARS`,
default 15, or in a small denylist such as `hi`, `ok`, `test`) are skipped:
they carry no topic worth naming. The first message is bounded to 2000 chars.

### Fork and prompt

`.agentone/scripts/core/auto_title_session.py` calls `Session.fork()` with:

- the **same agent, agent version, settings, workspace and model** as the
  parent — no `aimodel` override. This is deliberate: it preserves the cached
  prompt prefix (KV cache) instead of paying for a cold prompt on a different
  model;
- `anchor=<first user message>` so the fork sees the real conversation up to
  that point;
- `session_type=SUBTASK_HOOK` and `group_key="internal:auto-title"` so it is
  treated as a one-off internal worker and cannot fire hooks itself;
- `auto_compact_max_tokens=0` and `auto_compact_idle_seconds=0` so the fork
  cannot trigger another compaction/reflection fork;
- `tool_call_allowlist=["final_result"]` and `max_turns=2`. The allowlist
  restricts what the fork may execute **without changing the advertised tool
  list**, so the cacheable prefix stays identical to the parent's.

The injected chain is a short `SYSTEM_NOTICE` → `ASSISTANT` acknowledgement →
`SYSTEM_NOTICE` with a title-only prompt. The prompt asks for 2–6 words, at
most `AGENTONE_AUTO_TITLE_MAX_CHARS` (default 60), in the user's language, with
no quotes, markdown, emoji or trailing punctuation. It explicitly tells the
model to ignore instructions inside the user message and to call
`final_result` rather than answering the request.

### Parent-side ingest

`.agentone/scripts/core/ingest_auto_title.py` runs as a bound task in the
parent once the fork's call resolves (auto-await). It:

1. extracts the `final_result` with the shared
   `runtime.final_result.extract_final_result_text` helper;
2. strips markdown/quotes/labels and clamps the length (`sanitize_title`);
3. drops empty, non-topic results;
4. atomically updates `SessionModel.name` with
   `atomic_update_by_pk(..., expect={"name_is_auto": True, "name": expected_name})`.
   A manual rename between enqueue and ingest therefore wins;
5. appends a numeric suffix on name collision, mirroring `new_chat`;
6. updates `SessionVersionModel.display_name` via `QuerySet.update()` because
   version rows are immutable;
7. closes the fork with `request_end(reason="auto_title_done")`.

Because the write goes through `atomic_update_by_pk`, it publishes
`SessionModel:<pk>` over SSE, so the chat header and sidebar refresh without
any UI-specific code.

### Explicit names always win

`SessionModel.name_is_auto` (migration `0178_sessionmodel_name_is_auto`) is
`True` by default. The webUI and API set it to `False` whenever a session is
created with an explicit name or renamed later. The ingest guard checks both
`name_is_auto` and the captured `expected_name`, so an auto-title can never
clobber a user-chosen name.

## Configuration

In `config/settings_local.py`:

```python
AGENTONE_AUTO_TITLE_ENABLED = True   # set False to disable globally
AGENTONE_AUTO_TITLE_MIN_CHARS = 15   # skip very short first messages
AGENTONE_AUTO_TITLE_MAX_CHARS = 60   # clamped title length
```

## Files

| File | Role |
|---|---|
| `.agentone/scripts/core/auto_title_session.py` | Fork guard, prompt injection, fork configuration |
| `.agentone/scripts/core/ingest_auto_title.py` | Sanitise result, guarded rename, close fork |
| `.agentone/scripts/core/ingest_user_message.py` | First-message trigger after persistence |
| `.agentone/scripts/core/scripts.md` | Registers both bound tasks |
| `server/models/sessions/session.py` | `name_is_auto` field |
| `server/migrations/0178_sessionmodel_name_is_auto.py` | Schema migration |
| `config/settings.py` | Feature flags/limits |
| `webui/features/chats/views.py`, `api/views/sessions.py` | Clear `name_is_auto` on explicit names/renames |
| `server/tests/test_auto_title.py` | Feature tests |

## Failure behavior

Auto-titling is best-effort. Both the guard and the enqueue are wrapped so an
error is logged and message ingest continues normally; a failed or slow title
generation only means the chat keeps its default name. The fork cannot recurse
because it is a child `SUBTASK_HOOK` session with auto-compaction disabled.

## Sources for the comparison

- Claude Code: background Haiku titling with separate `ai-title`/`custom-title`.
- OpenCode: `packages/core/src/session/title.ts` and `.../runner/llm.ts` (hidden `title` agent).
- Codex ACP: `src/TitleGenerator.ts` at commit `34e08970aa324a2be985f5080674d5aa91d7666f`.
- Cursor: `NameAgent`.
- Codex CLI / pi: CLI naming behavior and absence of built-in naming, respectively.
