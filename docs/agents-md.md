# Workspace guidance files (e.g. `AGENTS.md`, `CLAUDE.md`)

**Status:** implemented (v1).

| Piece | Location |
|---|---|
| Core logic | `runtime/guidance_files.py` (no DB writes, no Celery) |
| Manifest keys | `registry/loader/load_agent_manifest.py` → `SettingsModel.autoload`, `SettingsModel.load_guidance_file_index`, `SettingsModel.guidance_file_index_limit` (migration `0133`) |
| Context injection | `.agentone/scripts/core/build_llm_context.py` (guidance-file autoload block after the system prompt) |
| Touch-hint hook | `runtime/tasks/bound_task.py` (`_maybe_append_guidance_hint`) |
| Compaction rules | `.agentone/scripts/compact/build_llm_compact_context.py` (compaction prompt) |
| Schema docs | `docs/manifest-format.md` ("Autoload" section), `docs/models.md` (SettingsModel fields) |
| Tests | `server/tests/test_guidance_files.py` (40 tests) |

**Scope:** read-only consumption of workspace guidance files into the LLM
context. No editing tooling, no `GEMINI.md` aliases, no global
`~/.agentone/` file in v1.

---

## 1. What it does

Guidance files are plain-Markdown "README for agents" files committed to a
repo (the industry `AGENTS.md` convention, stewarded at <https://agents.md/>)
that tell a coding agent how to work there — build/test/lint commands,
project layout, code style, boundaries, verification steps. A file applies
to its containing directory and all subdirectories; deeper files win on
conflict; explicit user instructions override everything.

AgentOne delivers this context through two independent mechanisms:

- **Autoload (pinned content).** The agent's `autoload:` patterns resolve
  against the session workspace once per session. Matched files are
  combined into one `USER` message placed right after the system prompt on
  every turn. Bytes are pinned: mid-session file edits take effect after
  the next compaction, never mid-turn. This is the slot for
  safety-critical rules — always in context, never dependent on model
  diligence.
- **Guidance-file index + just-in-time hints (advertise, don't push).**
  A count-capped index message lists nested guidance files (`AGENTS.md`,
  `CLAUDE.md`) that are *not* already pinned. When a successful tool call
  touches a subtree whose guidance has not been hinted yet, a one-line
  hint naming the file is appended to that call's result. The agent then
  reads the file itself through the normal `read` tool — fresh bytes, no
  speculative injection, no double-content. Either mechanism works without
  the other.

Why pinned + lazy: all major providers cache by exact prefix match, so
prefix bytes must be stable across turns. Re-resolving workspace files
every turn would bust the cache exactly when it matters most; the index
lives in the stable prefix while hints and agent reads arrive in the
growing history tail, where append-only growth is already cache-friendly.

---

## 2. Configuration (`agent.md`)

```yaml
autoload:
  files: [AGENTS.md, "docs/**/*.md"]  # workspace-relative path patterns
  maxFiles: 10          # default 10 — how many pattern matches load
  maxChars: 32768       # default 32768 — total chars of autoloaded content
  maxCharsPerFile: 8192 # default 8192 — per-file truncation cap
loadGuidanceFileIndex: true  # default true — index nested guidance files
guidanceFileIndexLimit: 10   # default 10 — max index entries (0 = omit index)
```

- The `autoload:` block and both index keys inherit through `extends` and
  resolve through the standard settings chain (session-overridable) like
  every other agent setting (`Agent.autoload`,
  `Agent.load_guidance_file_index`, `Agent.guidance_file_index_limit` and
  the `Session` counterparts delegate to the same chain).
- Invalid `autoload:` blocks fail the manifest load with a `ValueError`
  (non-mapping, unknown keys, empty entries, non-integer or negative
  budgets, non-boolean toggle). The removed `autoload.index` sub-key is
  rejected with a pointer to `loadGuidanceFileIndex`.
- `maxChars: 0` disables autoload contents; the index then lists
  everything, including the root file.

---

## 3. Pattern semantics

Implemented in `resolve_patterns` (`runtime/guidance_files.py`); validated
by `validate_autoload_block` at load time.

- Patterns are workspace-relative with glob language (`*`, `**`, `?`).
  No leading `/`, no `~`, no `..` — escaping patterns are rejected at
  load; symlink escapes and policy-denied files are skipped silently at
  resolve time.
- A bare filename (no slash, no glob) matches the workspace root only;
  any depth requires an explicit `**/` form (`**/AGENTS.md`).
- `*` / `?` never cross `/`; `**` crosses directories.
- Patterns evaluate in config order; matches within one pattern sort
  shallow-first, then lexicographically; dedup is by resolved path, so a
  symlink and its target count once. **Config order is priority order** —
  it decides what survives the caps and keeps turn bytes deterministic.
- Only files match; directories never do. Content decodes as UTF-8 with
  `errors="replace"` — undecodable content degrades, never fails the turn.
- Every match is gated by the resolved `access:` policy
  (`evaluate(policy, path, "read")`): `deny` → skip silently.
- Directory scans skip dot-directories and junk (`.git`,
  `__pycache__`, `node_modules`, …).

---

## 4. Runtime behaviour

### 4.1 Turn layout

`build_llm_context` inserts, immediately after the system-prompt block and
**outside** the `system_prompt_chain` guard (so prompt-less agents are
covered), before CUSTOM TOOLS:

1. agent `system_prompt_chain` (identity, SYSTEM),
2. autoloaded files — one `USER`/`TEXT` message, provenance headers per
   file (`## <workspace-relative path>`), omitted when empty,
3. guidance-file index — one `USER`/`TEXT` message, omitted when empty,
4. CUSTOM tools message (existing, when applicable),
5. conversation history — including touch-hints, the agent's own
   guidance-file reads, and the triggering user message.

Autoload / hint / index text is `TEXT`, never `TEMPLATE` — file bodies may
contain `{...}`/`{{...}}`.

The index intro drops its "already included in full above" parenthetical
when autoload produced no message, so the text stays truthful in every
combination.

### 4.2 Pin and repin (stale-until-compact)

`ensure_pinned(session)` returns the `(autoload_text, index_text)` pair:

- First call of a session resolves patterns, reads files, builds the
  index, and stores message bytes plus the index relpath list in the
  Django cache (`guidance:autoload:{pk}`, `guidance:index:{pk}`,
  `guidance:indexlist:{pk}`). Later turns reuse the bytes verbatim: zero
  FS reads on the hot path.
- Re-resolves when the latest `COMPACTION` message id changes
  (`guidance:marker:{pk}`) or the workspace path changes
  (`guidance:workspace:{pk}`) — i.e. repin on compaction, reset, or
  workspace switch. Post-compaction order is fixed: `system → freshly
  re-read files → rebuilt index → compaction summary → new turns`; where
  the summary and the fresh files disagree about workspace facts, the
  files win.
- The index `exclude` set covers exactly what is pinned — resolved but
  capped or unloadable files are *not* in context, so the index may still
  advertise them.
- Sessions without a workspace get `(None, None)` — no messages, no
  errors.
- `clear_guidance_cache(session_pk)` drops all six keys.

### 4.3 Touch hints (Path B)

`BoundTask._maybe_append_guidance_hint` runs after every successful
`(True, dict)` tool result, before the result is stored:

- Only filesystem-postured tools trigger (posture from
  `task_access_posture`; path args from `extract_path_args`). Shell /
  python tools are not hint triggers (see §8).
- Each target path resolves to its containing directory (files) or
  itself (directory reads/listings); outside-workspace paths are
  skipped. `chain_for_directory` yields the `root/…/target/AGENTS.md`
  ancestor chain, intersected with the cached index list.
- On a match, one line naming the *deepest not-yet-named* file on that
  chain is appended to the result payload under the `guidance_hint` key.
  The hinted-set (`guidance:hinted:{pk}`, a cached list) tracks both
  evaluated directories (`d:<rel>`) and already-named files
  (`f:<rel>`): a touched directory is evaluated once, and the same file
  is never named twice in a session — touching a sibling directory
  stays silent, while a still-unnamed deeper file on the chain is
  hinted normally. Serialisation into the `role="tool"` message carries
  the hint into history exactly once:

  ```
  [Note: foo/bar/AGENTS.md covers this directory — read it before continuing work here if you have not already.]
  ```

- **Explicit-read suppression:** when the agent reads an indexed guidance
  file itself, its directory is marked hinted with no hint appended —
  the content is already in context.
- The hook never raises; failures are logged and the result passes
  through unchanged.

### 4.4 Budgets (chars, not tokens)

- Per-file cap first (`maxCharsPerFile`, `[truncated: showing first N of
  M chars]` marker), then fill the total cap (`maxChars`) in config
  order, cutting the overflowing file to the remainder (`[truncated:
  file cut to fit the session autoload budget]` marker). Chars are exact
  and deterministic across models — determinism is the property prefix
  caching needs.
- `maxFiles` cuts the resolved list; the omitted count is logged.
- Index cap (`guidanceFileIndexLimit`): entries beyond the limit are
  replaced by a `(+N more — use glob **/{AGENTS.md,CLAUDE.md} to discover
  further)` line. Hint triggers consult the full discovery set, not the
  truncated list.
- Frontmatter counts toward the budget and passes through verbatim.

### 4.5 Failure semantics

Any discovery/read error skips that file and never fails the turn. A
transient read failure at pin/repin is "keep previous bytes" (pin) or
"skip the file" (repin), never deletion; a clean absence at repin drops
the file. No pattern matches and empty index → zero messages added,
byte-identical behaviour to a session without guidance support.

---

## 5. Trust boundary

Workspace files are untrusted input (any workspace writer, human or tool,
can modify them; prompt-injection via guidance files is the primary
risk). Mitigations in place:

1. **Provenance labelling** — both wrappers mark content as advisory
   workspace guidance, explicitly *not* a change to tools/permissions.
2. **No privilege escalation by content** — guidance is natural language
   only; it cannot alter tool allow-lists, `access:` policy, approval
   posture, or model selection.
3. **Access-policy gating** — `deny`d files never reach context (content
   or index).
4. **Auditability** (§6).

---

## 6. Observability

- The autoload and index sections are regular `QueryMessage`s, visible in
  the API `queries/` endpoint and as query cards in the UI
  (`publish_model_event(query, "create")`).
- Hints ride in the tool call's stored result (`guidance_hint` key),
  visible in history and `role="tool"` messages.
- Injection failures log one `DebugLogEntry(event="guidance_skip", …)`
  with the traceback; per-file skips (deny-policy, symlink-escape,
  unreadable) go to the service log. Nothing is surfaced to the user in
  chat.

---

## 7. Compaction interaction

The compaction prompt (`.agentone/scripts/compact/build_llm_compact_context.py`)
carries two rules: **exclude** autoloaded file contents from the summary
(they reload automatically; a restated copy would waste context and be
immediately stale), and **record** which guidance files were consulted and
what was decided under them (so the post-compact session keeps the
"why"). The hinted-set is cleared on repin, so post-compaction turns
re-hint live subtrees on next touch rather than assuming the summary
retained them.

---

## 8. Known limitations

- `read_image` is declared `access: read` but missing from
  `PATH_ARG_NAMES`, so neither the access check nor the hint trigger
  fires for it.
- Shell/python tools are not hint triggers: they take no path arguments
  and their embedded paths are only classified for access control, not
  extracted per call. Agents that work in one directory should use
  absolute paths with file tools, or guidance arrives via the index
  instead of a just-in-time hint.
- No frontmatter parsing (passes through verbatim, counts toward the
  budget), no `GEMINI.md` alias, no global `~/.agentone/` file, no
  `AGENTS.override.md` convention, no write tooling.

---

## 9. Future work

- Frontmatter-based selective loading (`description`/`tags`/`paths`
  relevance ranking over the plain index). Hazard: a selector must never
  become a second representation of bytes the prefix already carries —
  select *between* candidates, never duplicate one already sent.
- Exact (tokenizer-based) budget accounting per provider/model to replace
  the char ruler; Hermes-style dynamic caps scaled to the session model's
  context window.
- Explicit provider cache control (Anthropic `cache_control`
  breakpoints + `prompt_cache_key` = session id) now that prefix
  discipline makes them effective.
- Authoring tooling: template scaffolder, `Never`-rule lint, staleness
  nudge when listed test commands fail.

---

## 10. Tests

`server/tests/test_guidance_files.py` (40 tests):

- Manifest validation: defaults, `str`→list, unknown keys, `/`/`~`/`..`
  rejection, bad budgets, legacy `index` sub-key rejection.
- Pattern semantics: root-only bare names, `**/` recursion, `*` not
  crossing `/`, config-order priority + dedup, `maxFiles` cut with
  omitted count, directories never matching, deny-policy skips, symlink
  escape skips.
- Loading: per-file and total truncation markers, `maxChars: 0`,
  unreadable-file skip.
- Index: pinned-path exclusion, limit + remainder, `0` limit, deny
  omission, shallow-first determinism.
- Loader round-trip (`autoload_ok` / `autoload_bad` fixture agents) and
  `extends` inheritance.
- Session behaviour: pin stability across turns, index disabled
  independently of autoload, index without autoload content, hint-once
  then silent, explicit-read suppression, full `build_llm_context`
  injection order and roles.

---

**See also:** [Architecture](architecture.md) ·
[Core mechanisms](core-mechanisms.md) · [Manifest format](manifest-format.md)
· [Development guide](development.md) · <https://agents.md/>
