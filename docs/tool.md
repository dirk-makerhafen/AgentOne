# Tools

Tools are LLM-callable functions declared in `scripts.md` manifests. They follow the same format as tasks and commands.

## Quick reference

```yaml
tools:
  - name: read
    file: filesystem.py
    function: read
    bound: True
    requires_approval: false
```

## Full documentation

See [docs/manifest-format.md](manifest-format.md) for the complete manifest format reference, including tools, tasks, commands, chains, groups, maps, and scripts.

## Ad-hoc tools (session-private, unregistered)

Agents with `adhoc.*` in their tool allowlist can create throwaway single-function
helpers for the current session — no manifest edit, no `reload_all`:

- `adhoc_create(name, source, description, params_schema?)` — source must
  define `def run(...)` with a normal signature
  (`def run(text: str, limit: int = 10)`) whose parameters become keyword
  arguments. `params_schema` is optional — it is inferred from the
  signature. `run` may return anything JSON-safe; auto-allowed but
  safety-scanned (same Python guardrails as the `execution.python` tool
  plus a workspace-policy path check).
- `adhoc_list` / `adhoc_read` — discover and inspect (metadata only in list).
- `adhoc_update` / `adhoc_delete` — mint a new version / remove the link.
  A source-only update refreshes an inferred schema; an explicit schema
  is never clobbered.
- `adhoc_function_call(adhoc_tool_name, **kwargs)` — the **only** way to
  execute one (isolated subprocess, 60s timeout, truncated output).
  Result is namespaced under `result`.

Storage is database rows, same pattern as query templates
(`server/models/queries/query_template.py`): immutable `AdhocToolVersion`
rows point at content-addressed `GenericContent` (identical code dedupes
across sessions); a session's current tool is a `SessionAdhocTool` link row,
unique per session + name. Every save mints a version and moves only the
writer's link; forks inherit the parent's links copy-on-write (hook in
`AgentVersionModel.get_or_create_session`); deletes remove the link only,
leaving versions as the audit trail (never GC'd in v1). Sources are scanned
once at write time — reads never re-scan. Archive is a visibility state,
not a freeze: tools keep working on archived sessions.
Implementation: `server/models/adhoc_tool.py` + `runtime/adhoc_tools.py`
(wrappers in `.agentone/scripts/adhoc/adhoc.py`); tests in
`server/tests/test_adhoc_tools.py`. There is no promotion path yet — that is
a separate future layer.