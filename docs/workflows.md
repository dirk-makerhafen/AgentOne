# Session-Private Dynamic Workflows (Proposal — not implemented)

Status: proposal only. No code has been written for this yet.

## 1. Goal

Let an agent **create a workflow during a session**, **execute it**, and keep it
**session-private initially**. A workflow is a combination of tool calls
supporting sequential steps, parallel groups, and fan-out maps, plus simple
conditionals.

Agreed decisions (planning session):

- DSL: linear steps + `group` + `map` (covers for_each) + `when` conditionals.
  No per-step retries (underlying tools already carry `max_retries` /
  `RATE_LIMITED` handling).
- Execution: non-blocking chained dispatch (no worker blocking).
- Invocation: single generic wrapper tool `workflow_run(name, inputs)`.
  Workflows never become native LLM tools in V1.
- Storage: **database-backed with versioning**, mirroring query templates and
  ad-hoc tools. No filesystem storage.
- Promotion/export to project/global manifests: out of V1.

## 2. Building blocks (reuse)

- Static `chain` / `group` / `map` in `scripts.md`
  (`docs/manifest-format.md`, `server/models/tasks/agent_task_run.py`).
  Static only — baked into immutable `TaskDefinitionVersion` rows via
  `reload_all`. Not usable for runtime creation.
- Session-private DB pattern (the template to copy):
  - Query templates: `server/models/queries/query_template.py`
    (`QueryTemplateVersion` immutable + `SessionQueryTemplate` link) +
    `runtime/query_templates.py` (validation, version minting,
    identical-content no-op, `inherit_templates`).
  - Ad-hoc tools: `server/models/adhoc_tool.py`
    (`AdhocToolVersion` + `SessionAdhocTool`) + `runtime/adhoc_tools.py`
    (same structure: paths → validation → CRUD → call/inherit).
  - Content-addressing: `server/models/content.py` (`GenericContent.from_data`
    / `from_text` — identical bodies dedupe across sessions).
  - Fork inheritance: `AgentVersionModel.get_or_create_session`
    (`server/models/agents/agent_version.py`) calls `inherit_templates` /
    `inherit_adhoc_tools` for newly created sessions (copy-on-write, no
    versions minted).
- Dispatch primitives (`docs/core-mechanisms.md`):
  - `BoundTask.delay()` → `TaskInstance` → `AgentTaskCall` → `AgentTaskRun`
    (`runtime/tasks/bound_task.py`).
  - Non-blocking ordering via arg dependencies: passing an `AgentTaskCall` as
    an argument parks the consumer in `WAITING_DEPENDENCY` until the producer
    ends (same pattern as `ingest_subagent_result` /
    `delegate_task(blocking=False)`).
  - Parallel fan-out auto-await via result refs: returning `AgentTaskCall`s
    puts the run in `WAITING_RESULTTASKS` and substitutes results.
  - Static map precedent: producer result (list) + `map` bound task
    (`.agentone/scripts/core/map.py`) fanning out `consumer.delay(item)`.
- Isolation: session links are per-session rows; the workspace guardrail
  (`runtime/workspace_access.py`) already denies cross-session access.
  The session-private folder still exists for scratch *tool args*, but
  workflows themselves never touch `runtime/session_folder.py`.

## 3. Data model

New models (location TBD: `server/models/workflows/` or a single
`server/models/workflow.py`, matching `adhoc_tool.py`):

- `WorkflowVersion` (immutable — `save()` raises on update):
  - `content` FK → `GenericContent` (`PROTECT`; `from_data()` canonicalizes
    with `sort_keys=True` itself, so identical definitions dedupe across
    sessions),
  - `name` denormalized CharField,
  - `created_by_session` FK → `SessionModel` (`SET_NULL`, audit only),
  - `source` CharField (`tool`, `migrate`, …).
- `SessionWorkflow` (the link row):
  - `session` FK → `SessionModel` (`CASCADE`),
  - `name`, `version` FK → `WorkflowVersion` (`PROTECT`),
  - `UniqueConstraint(session, name)` (`uniq_session_workflow_name`),
  - observable key `SessionWorkflow.session:<pk>` for future UI (V1 needs no
    panel).

Lifecycle (same as templates/adhoc):

- Save → validate → store versioned: link already pointing at identical
  `content_id` is a no-op (no new version); else mint version row and
  `update_or_create` only the writer's link. Siblings/forks keep theirs.
- Delete → delete the link row only; version rows stay as the audit trail.
- Fork → `inherit_workflows(parent_pk, child_pk)` (copy-on-write, no versions
  minted), called from `get_or_create_session` next to the existing
  `inherit_templates` / `inherit_adhoc_tools` calls.
- Archived session → refuse create/update/delete/run; allow list/get for
  audit. No shared helper exists anymore (`_refuse_if_archived` was removed
  from `runtime/adhoc_tools.py`) — add a small local helper.

## 4. Runtime module (`runtime/session_workflows.py`)

Mirrors DB-era `runtime/query_templates.py` / `runtime/adhoc_tools.py`:
validation (no DB) + DB functions with the same style. All take raw session
pks except the thin tool wrappers (duck-typed session).

- `validate_workflow_name` — `^[a-z][a-z0-9_]{2,40}$` (same as adhoc).
- `parse_workflow_dict` — steps well-formed, `id`s unique identifiers,
  `tool` names, `group` (2+ branches) / `map` shapes, `when` grammar (see §6),
  template variables resolve against `inputs` + prior steps + `item`/`index`
  only (Jinja `StrictUndefined` — typos fail loudly, same strictness as query
  templates).
- `list_workflows(session_pk)` — metadata only (name, description, version
  pk, step count) to keep context small.
- `get_workflow(session_pk, name)` — full parsed definition + version pk.
- `save_workflow(session_pk, name, steps, description, inputs_schema,
  source="tool")` — validate, canonicalize (`json.dumps(sort_keys=True)`),
  identical-content no-op, else mint + move link under
  `transaction.atomic()` with `select_for_update` (same race handling as
  `update_adhoc_tool`).
- `delete_workflow(session_pk, name)` — link only.
- `inherit_workflows(parent_pk, child_pk)` — bulk link copy,
  `ignore_conflicts=True`.
- Caps: 20 workflows/session, 64KB canonical JSON, ≤32 steps, ≤2 composite
  nesting levels, `when` ≤200 chars, map fan-out default 8 / hard cap 32,
  10KB per rendered arg.

## 5. DSL (V1)

A workflow is an ordered `steps` list. Each step has an `id`, exactly one
action (tool call, `group`, or `map`), and an optional `when` conditional.

```json
{
  "name": "triage_inbox",
  "description": "Summarize new items then file them in parallel",
  "inputs_schema": {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]},
  "steps": [
    {"id": "fetch", "tool": "inbox_search", "args": {"query": "{{ inputs.topic }}", "limit": 20}},
    {"id": "per_item",
     "map": {
       "producer": {"step": "fetch"},
       "consumer": {"tool": "summarize_text", "args": {"text": "{{ item.body }}"}},
       "item_var": "item", "max_parallel": 8
     }},
    {"id": "notify",
     "group": [
       {"tool": "file_write", "args": {"path": "/tmp/report.md", "content": "{{ steps.per_item.output }}"}},
       {"tool": "send_message", "args": {"text": "filed {{ steps.per_item.count }} items"}}
     ]},
    {"id": "escalate", "tool": "send_alert", "args": {"text": "high priority found"},
     "when": "steps.per_item.output contains high_priority"}
  ]
}
```

Semantics:

- **Sequence (default):** steps run in order with templated args.
- **`group`:** 2+ tool invocations fired with the same resolved context, in
  parallel. Result = outputs in branch order. Optional
  `"tolerate_failures": true` returns per-branch `{ok, output/error}`
  instead of failing the step. Analogue of static `GROUP`.
- **`map` (the for_each):** `{producer, consumer, item_var?, max_parallel?}`.
  Producer is `{"step": "<prior_id>"}` (must resolve to a list) or an inline
  tool call returning a list. Consumer is one tool template applied per
  element with `{{ item }}` (+ `{{ index }}`) bound. Empty list → skipped,
  output `[]`. Overflow beyond `max_parallel` goes through successive
  continuation waves. Analogue of static `MAP` + `map.py`.
- **Nesting:** `group` branches and `map.consumer` may contain one nested
  `group`/`map`. Arbitrary DAGs / `depends_on` graphs are out of V1.
- **Failures:** a failed step fails the workflow (result carries
  `failed_step` + tool error), except `when`-guarded skips and
  `tolerate_failures` groups. No per-step retry/timeout overrides in V1.

## 6. Conditionals (`when`)

Restricted predicate string — no new expression language, no arbitrary
`eval()`. Evaluated in the continuation task *after* dependencies resolve,
so it sees real outputs:

```
"when": "<operand> <operator> <literal> [and/or ...]"
```

- Operand: `steps.<id>` (with `succeeded` / `failed`) or
  `steps.<id>.output` path with dotted/key access
  (e.g. `steps.check.output.status`, `steps.per_item.count`).
- Operators: `== != > >= < <=`, `contains`, `not contains`, `is empty`,
  `is not empty`, `succeeded`, `failed`.
- Literal: quoted string, number, boolean, `[]`/`{}`. No function calls,
  max ~200 chars.
- Examples:
  - `steps.check.output.status == "error"`
  - `steps.per_item.count > 0 and steps.fetch succeeded`
  - `steps.per_item.output contains high_priority`
- A falsy `when` **skips** the step (journal records
  `{"skipped": true, "when": ...}`; downstream
  `{{ steps.<id>.output }}` resolves to `null`). No `else` in V1 — write
  the complementary predicate on a second step.
- Validation is static: unknown step refs, forward references, and type
  mismatches (e.g. `>` on a dict) are create/update/validate-time errors.

## 7. Tool surface (wrapper invocation)

All bound (`_session` first) in `.agentone/scripts/workflow/workflow.py` +
`scripts.md`, thin forwards to `runtime/session_workflows.py` (same split as
`adhoc.py` / `adhoc_tools.py`):

| Tool | Purpose |
|---|---|
| `workflow_create(name, steps, description?, inputs_schema?)` | Validate + save (fail-if-exists; upsert lives in update). |
| `workflow_update(name, steps?, description?, inputs_schema?)` | Re-validate; identical content is a no-op (`unchanged: True`); else mints a new version and moves only the writer's link. |
| `workflow_list()` | Metadata only. |
| `workflow_get(name)` | Full definition (debug/iterate). |
| `workflow_delete(name)` | Remove link only (refuse while a run is in flight). |
| `workflow_validate(name \| inline steps)` | Dry-run validation without writing/running. |
| `workflow_run(name, inputs?)` | Validate inputs vs schema, pin `version.pk`, dispatch step 1, return the `AgentTaskCall` (auto-awaited, so the LLM turn receives the final result — same as `template_execute`). |

The LLM never calls workflow steps directly. Each step's tool goes through
`session.get_tool(name).delay(...)`, so **approvals, workspace-policy
checks, and rate limits apply per sub-call unchanged**. A `deny` fails that
step; an `ask` parks the sub-call in `HALTED_APPROVAL` and the workflow
waits.

## 8. Execution (non-blocking chained, version-pinned)

`workflow_run` writes no journal row — run state lives in the
`AgentTaskCall`/`AgentTaskRun` graph. It pins the version pk (mid-run edits
don't change semantics) and dispatches `workflow_step` for step 1:

- **Single tool step:** `workflow_step(run_ctx, step_id)` resolves templates
  → `session.get_tool(t).delay(args)` → dispatches
  `workflow_advance(run_ctx, step_id, tool_call)` with the call as an
  `AgentTaskCall` arg → scheduler parks it in `WAITING_DEPENDENCY` until the
  tool ends → advance evaluates the next step's `when` and dispatches the
  next `workflow_step` (or returns the final output ref so
  `WAITING_RESULTTASKS` resolves the whole workflow).
- **Group:** dispatch N tool calls, then `workflow_join(run_ctx, step_id,
  call_1, …, call_N)` with all N as args — the join fires only when every
  branch ends (multi-arg `WAITING_DEPENDENCY` fan-in).
- **Map:** dispatch the producer → `workflow_fanout(run_ctx, step_id,
  producer_call)` (waits on producer) → resolve list → dispatch up to
  `max_parallel` consumer steps + a join over them; overflow loops through
  further fanout waves.
- Continuations resolve refs with `timeout=0` (safe — the dependency
  guarantees the call ended) and read the definition from the pinned
  immutable version (no re-read race). Worker occupancy per task is
  milliseconds; nothing calls blocking `get_result()` inside a worker.
- `ContextTracker` parent links are preserved (every dispatch happens
  inside a run), so the full tree stays visible in the `task-calls/` API.
- Workflows may call `workflow_run` as a step (composition) with a
  `visited` stack in `run_ctx`: max depth 3, cycle → error.
- Delete-mid-run is safe: continuations hold the pinned `version.pk`, not
  the link.

## 9. Validation / security

- Write time: name regex, JSON size, step/depth caps, `when` grammar, template
  vars, tool-name allowlist (warn at save — allowlists can change).
- Run time: tool must still be in `session.allowedToolNames` (else clear
  error); absolute-looking rendered args checked against the workspace
  policy; literal `sessions/<other_pk>` rejected; `map.producer` must yield
  a list.
- No new code execution: workflows compose only already-registered tools,
  so the Python/shell guardrail surface does not grow. Sub-calls inherit
  their own `requires_approval` / posture enforcement.

## 10. Explicitly out of V1

Promotion/export, native tool-schema injection, per-step retries, `else`
branches, DAG/`depends_on`, cron triggers on workflows, UI panel, and a
`WorkflowRun` table (revisit if cancel/resume UI is needed — run state
currently lives in the call graph).

## 11. Testing / rollout

- Unit: DSL parser/validator matrix, template resolution (`StrictUndefined`
  failures), `when` truth table, caps.
- Model: version immutability, identical-content dedupe no-op, link-only
  delete, fork inheritance, archived refusal (new behavior — no existing
  test to mirror; structure the rest after
  `server/tests/test_query_templates.py`).
- Integration (ephemeral sessions): sequence → group → map → conditional
  skip → nested workflow (depth guard), approval-parked sub-call,
  archived-session refusal, delete-mid-run survival.
- Work: new models + migration (+ admin registration), new
  `runtime/session_workflows.py`, new `.agentone/scripts/workflow/` wrappers,
  `inherit_workflows` hook in `get_or_create_session`, tests, and this doc.
  No loader, scheduler, or `build_llm_context` changes.
