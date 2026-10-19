# UI data requirements — components, data needs, and subscriptions

> Purpose: inventory of what the current pyHtmlGui UI (`ui/`) needs
> (initial data + live updates) so a UI migration can be scoped against the
> REST API surface (`api/`). Generated 2026-10-12 from source audit.
> Mechanism reference: `docs/observables-migration.md`,
> `runtime/observables.py`, `runtime/events.py`, `ui/consumer.py`,
> `ui/lib/model_view.py`.

## 0. How live updates work (1 paragraph)

Producers call `publish_model_event(instance, action)` (`runtime/events.py:47`),
which calls `instance.notify_observers(action)`. `ObservableMixin.observable_keys()`
(`server/models/base_model.py:75`) derives keys: any-key (`<Model>`), pk-key
(`<Model>.pk:<pk>`), plus one key per set FK (e.g. `Message.session:7`).
`runtime/observables.py:88 notify()` RPUSHes one message per subscribed UI
instance to `agentone:uiq:<instance_key>`. Each websocket instance runs one
drain thread (`ui/consumer.py:55 loop`, `BLPOP timeout=5`, coalesce
last-message-wins per `function_id`). Views subscribe via
`orm_subscribe(view, key, callback)` (`ui/lib/model_view.py:17`) and
unsubscribe via `orm_unsubscribe_view`. Only **12 call-sites** subscribe
(see §1); everything else renders once and re-renders on user action,
`refresh_from_db()`, or JS polling.

Current REST API (for the coverage column): `api/urls.py` exposes
`agents`, `sessions`, `queries`, `collections`, `cron`, `providers`,
`models`, `skills`, `projects`, `systems`, `task-calls`, `task-runs`,
`workspaces` (+ `health/`, `me/`, `auth/token/`). Notable extras:
`GET sessions/{id}/messages` (paginated), `POST sessions/{id}/message`,
`GET sessions/{id}/tasks`, `POST sessions/{id}/call/{task_name}`,
`POST sessions/{id}/reset`, `POST queries/{id}/cancel`,
`POST task-calls/{id}/approve|deny|answer`. There is **no**
`workitems`, `terminals`, `logs`, `insights/analytics`, or `messages`
top-level endpoint, and **no websocket/SSE** push channel.

---

## 1. Live-subscribed components (all `orm_subscribe` call-sites)

Only these re-render without user action. A replacement UI must either
poll the listed REST endpoint(s) or add a push channel (websocket/SSE)
carrying the same `(model, pk, action)` triple.

| # | Component (file:line) | Initial data needed | Subscribes to (key → filter) | Actions handled → UI behavior | REST equivalent today | Gap |
|---|---|---|---|---|---|---|
| 1.1 | `Messages` — `ui/main/chat/messages/messages.py:102-109` | Last ≤100 `Message` via `prev_message` chain from `Session.get_last_message()` (`:159-174`); per message `related_queries.filter(session_version__session=sid).order_by(-pk)`; window paging via `up()` (`prev_message`, trim tail `:337-354`), `down()` (`next_messages.filter(session_version__session).first()` `:356-379`), `jump_to_message(pk)` | `Message.session:<sid>`, `Query.session:<sid>`, `AgentTaskCall.session:<sid>` → `_on_orm_event:208-220` | `Message/create` → `_on_message_created:222-257` (fetch `Msg(pk)`, dedup, insert after `prev_message_id` else append + append related queries); `Query/create` → insert after `trigger_message_id`; `Query/update` → `refresh_from_db + view.update()`; `AgentTaskCall/update` → find `ToolCard` by pk, `refresh_from_db + update()` | `GET sessions/{id}/messages` (paginated, ordered by `created_at`); `GET queries?session=<sid>`; `GET task-calls?session=<sid>` | Partial. No single-message GET; no `status_detail` filter on task-calls; no push — must poll `messages` + `queries?session` + `task-calls?session` |
| 1.2 | `ComposerFooter` (busy/mode pill) — `ui/main/chat/composer/footer.py:310-332` | No queryset. `Session.is_busy()`, `send_mode` (`send/queue/interrupt/steer` from queued count `:274-290`), `status_text` = `AgentTaskCall.filter(session, WAITING_QUEUE).count()` `:293-308` | Same 3 session keys → `_on_activity_event:338-351` | Re-`update()` **only if** `(is_busy, send_mode)` flipped (avoids collapsing open dropdowns on every FSM transition) | Same three GETs as 1.1 | Partial. Needs `task-calls?session=&status=` + busy derivation; poll-friendly (cheap boolean) |
| 1.3 | `ApprovalCard` — `ui/main/chat/cards/approval.py:63-78` | `Session.needs_approval()` (turn counters); on approve `get_messages().order_by(-pk).first()` | `SessionModel.pk:<sid>` → `_on_orm_event:80-83` | `SessionModel/update` → full `update()` (toggles `visible` class) | `GET sessions/{id}` (detail serializer) + `POST sessions/{id}/reset` | Mostly covered, **if** detail serializer exposes `needs_approval` / turn counters — verify. Push missing |
| 1.4 | `QueueCard` — `ui/main/chat/cards/queue.py:48-63` | `AgentTaskCall.filter(session, status_detail=WAITING_QUEUE).order_by(created_at)`; `queue_count`, `call.aimodel.name` | `AgentTaskCall.session:<sid>` → `_on_orm_event:65-72` | `create/update/delete` → `update() + _sync_pill()` (JS updates `.queue-pill-outer` count) | `GET task-calls?session=<sid>` | **Gap: no `status_detail` filter** (`TaskCallFilter` only has `session,status,task_name`). Client must fetch all session calls and filter `status_detail==WAITING_QUEUE` locally |
| 1.5 | `QuestionCard` (ask_user) — `ui/main/chat/cards/question.py:105-117` | `AgentTaskCall.filter(session, status_detail=HALTED_APPROVAL, task_definition__name=ask_user).select_related(...)[:3]` + `normalize_questions` answers dict `:120-163` | `AgentTaskCall.session:<sid>` | `update` → `update()` | `GET task-calls?session=<sid>&task_name=ask_user` + `POST task-calls/{id}/answer` | **Gap: no `status_detail` filter**; answer action exists |
| 1.6 | `GuardrailApprovalCard` — `ui/main/chat/cards/guardrail_approval.py:72-84` | `AgentTaskCall.filter(session, HALTED_APPROVAL).select_related(...)[:5]` + `task_definition_version.task_definition.name, auto_review_status, guardrail_reason, carguments_json` `:87-94` | `AgentTaskCall.session:<sid>` | `update` → `update()` | `GET task-calls?session=<sid>` + `POST task-calls/{id}/approve|deny` | **Gap: no `status_detail` filter**; approve/deny exist |
| 1.7 | `RateLimitCard` — `ui/main/chat/cards/rate_limit.py:135-148` | Snapshot `_compute:207-224`: `AgentTaskCall.filter(session, WAITING_RATELIMIT).order_by(created_at)`; blocked aimodel (`session.aimodel` else first parked call's pinned version); `ApiKey.rate_limit_until`, `api_provider.api_keys.filter(enabled)`, sibling aimodels, `model_groups()[:6]`, `KeyFailoverPolicy` | `AgentTaskCall.session:<sid>` → unconditional `update()` | `update()` + snapshot clear; **only `set_autoupdate_interval(2)` user in `ui/`** (`:198-205` — 2s server-push countdown while `pending_count>0`) | `GET task-calls?session=<sid>` + `GET providers/`, `GET models/` | **Gaps: no `status_detail` filter; no rate-limit/ApoKey `rate_limit_until` endpoint; no push — needs 2s poll** |
| 1.8 | `CtxIndicatorWrap` (context ring) — `ui/main/chat/composer/wrap/ctxindicator.py:54-69` | `Session.context_usage()` → `used_context_percent/tokens, max_context_tokens, tokens_send/received/cached, reasoning` `:71-72` | `Query.session:<sid>` → `:105-111` | `Query/update` → `update()` (ring refresh) | None | **Gap: no context-usage endpoint.** Would need `GET sessions/{id}` to expose token counters, or a new `GET sessions/{id}/usage` |
| 1.9 | `ChatTocView` — `ui/main/chat/toc.py:60-72` | `_reload_segments:90-111`: `Message.filter(session_id=sid, message_type=compaction).values_list(pk)` then `Message.filter(pk__in).order_by(pk)`; cached + `compaction_pks` JSON | `Message.session:<sid>` → `:119-132` | `Message/create` + `Message.filter(pk, message_type=compaction).exists()` → invalidate cache + `update()` | `GET sessions/{id}/messages` includes `parts` (`MessagePartSerializer`) | Message serializer does not expose `message_type` client-side; client filters locally. Push missing |
| 1.10 | `WorkItemsBoard` — `ui/main/workitems/board.py:209-241` | `scoped_queryset` (`board_data.py:51-67`): `WorkItem.all()[.filter(project_id)].select_related(assigned_agent).order_by(-priority, created_at)`; client filters `show_terminal/agent/verify/only_actionable`; `grouped/counts/empty_board/selected/children (WorkItem.filter(parent_id))`; `scope_label: Project.filter(pk).values_list(name)`; `agent_options` | `WorkItem` **any-key** (every `WorkItem` write) → `_on_orm_event:233-241` | Clear `_rows_cache/_rows_signature/_scope_label_cache` + `update()` | None | **Biggest gap: no `/workitems` endpoint at all.** Needs new CRUD + list `?project=` + children `?parent=` |
| 1.11 | `SidebarPanelWorkspaces` — `ui/sidebar/panels/workspaces.py:140-149` | `WorkspaceModel.objects.all()` → `build_workspace_tree` (path-prefix parents); `current_workspace_pk`, `active_workspace_pk` via `current_session_workspace_pk(main_panel)` | `WorkspaceModel` **any-key** → `:203-205` | Unconditional `update()` | `GET workspaces/` (full CRUD in `WorkspaceViewSet`) | Covered for data; push missing (poll or new SSE) |
| 1.12 | `RightPanelSessionTemplates` (run poll) — `ui/main/rightpanel/session/rightpanel_session_templates.py:247-284` | `list_templates(session_pk)`, `get_template`, local `_values/_preview/_error`; on run `AgentTaskCall.objects.get(pk=_run_call_pk)` | **Dynamic, only while a template run is active:** `AgentTaskCall.session:<sid>` (`runTemplate:256`) → `_on_orm_event:277-284` (`pk==_run_call_pk` → `_refresh_run + update()`); `_unsubscribe_run:326-332` on done | Transient subscription, not a permanent feed | `GET task-calls/{id}` + `POST sessions/{id}/call/{task_name}` | Covered for polling the single call; push missing |

## 2. Polling / JS-timer components (no `orm_subscribe`)

| Component | File | Data needed | Current mechanism | REST equivalent / gap |
|---|---|---|---|---|
| `RateLimitCard` countdown | `ui/main/chat/cards/rate_limit.py:198-205` | Same as §1.7 | `set_autoupdate_interval(2)` while pending > 0 | Poll `GET task-calls?session=` every 2s while rate-limited |
| Logs auto-refresh | `ui/sidebar/panels/logs.py:37`, `ui/main/logs/logs.py:11-32` | Log file list + tail (selected file, line count) | JS checkbox → `fetch` poll every 5s into `#logsOutput` | **Gap: logs are not in DRF** — check what fetch URL the JS uses; needs new `GET /logs` or reuse |
| Power status | `ui/main/settings/panels/preferences.py:54-79` | Power/battery status | JS `setInterval(refreshPowerStatus, 30000)` | Browser API, not server data — no REST needed |

## 3. Static / manual-refresh components (render once, update on user action)

These never subscribe; a new UI fetches on navigation/tab-open and refetches
on mutation. Grouped by area.

### 3.1 Chat shell (container + message rows + banners + composer)

| Component | File | Data needed (initial) | Mutations it issues | REST equivalent |
|---|---|---|---|---|
| `Chat` container | `ui/main/chat/chat.py:25-96` | `Session` runtime wrapper (`SessionModel` + `Session(session)`) | — (container) | `GET sessions/{id}` |
| `MessageView` router | `ui/main/chat/messages/message.py:15-92` | `Message \| Query` subject; `fork(message_id)` → `Message(pk)` + `Session.fork(...)` + open tab | `fork` (creates child session) | `GET sessions/{id}/messages` then client split; fork needs new endpoint or `POST sessions/` + link |
| `AssistantMessageView` | `ui/main/chat/messages/assistant_message.py:13-116` | `parts.filter(tool_call__isnull=False)` → `AgentTaskCall.filter(pk__in)` → `QuerySetView(tool_calls, ToolCard)`; template reads `session_version.agent.name`, `response.{completion_tokens, time_to_first_token, reasoning_time, token_generation_time, total_time, reasoning}`, `parts.filter(type__in=[MESSAGE])` | — | `GET sessions/{id}/messages` (parts + tool_call ids) + `GET task-calls?session=` + `GET queries?session=` |
| `User/InfoMessageView` | `user_message.py`, `info_message.py` | `parts.all()` (+ `content_type==IMAGE` branch) | — | Same messages GET |
| `QueryView` | `ui/main/chat/messages/query.py:11-60` | `related_query_messages.order_by(pk)` on toggle + `session_version.get_runtime().aimodel.requires_reasoning_echo` | toggle (local) | `GET queries/{id}` (detail) |
| `ToolCard` | `ui/main/chat/messages/toolcard.py:10-69` | `_resolve_call_arguments()`, `get_result(allow_partial_results=True)`, `status/status_detail`; `approve/deny → CallScheduler.approve/deny_taskcall` (updated via parent `Messages._on_taskcall_updated`, no own subscribe) | approve / deny | `GET task-calls/{id}` + `POST task-calls/{id}/approve|deny` — covered |
| `ClarifyCard` | `ui/main/chat/cards/clarify.py:8-54` | None (static hidden shell, JS `respondClarify()`) | JS-only | None needed |
| Banners (health/reconnect/update) | `ui/main/chat/banner/*.py` | None (JS: `dismissAgentHealthAlert`, `refreshSession`, `applyUpdates/forceUpdate`) | JS-only | `GET health/` for health banner |
| `ComposerBox` + command dropdown | `ui/main/chat/composer/box.py`, `dropdown/command.py` | `UiApp.settings.send_key`; static command list + in-memory `ObservableListView` filter | — | `GET me/` / settings (check); commands are client-side |
| Model/profile/reasoning/toolsets/workspace dropdowns + wraps | `ui/main/chat/composer/dropdown/{model,profile,reasoning,toolsets,workspace}.py`, `wrap/*.py` | `Session` runtime: `aimodel`, `workspace`, `allowed*Names`; option lists `AiModel` / `WorkspaceModel` | `set_model_group / set_specific_provider / toggle / close / _refresh_selection` (session settings writes) | `GET models/`, `GET workspaces/`, `GET sessions/{id}/tasks`, `PATCH sessions/{id}` (aimodel/reasoning/etc.) — mostly covered |
| `TerminalPanel`, `MobileConfigPanel` | `ui/main/chat/panel/terminal.py`, `panel/mobileconfig.py` | Pure xterm/JS shells, no ORM | tmux via `list_terminals` / `poll_output` | **Gap: no terminal endpoint.** Needs new `GET/POST sessions/{id}/terminals` |
| `ChatsOverview` (new-chat page) | `ui/main/chat/overview.py:27-314` | `AgentModel.filter(parent_skill=None, parent_agent=None, parent_project=None).order_by(name)` + `is_user_visible`; `agent_options: AgentModel.all().order_by(name)[visible]`; `workspace_options: WorkspaceModel.all()`; `_recent_chat_qs:179-194` = `SessionModel.filter(parent_session__isnull, SESSION, archived=False)[+workspace preset].select_related(latest_session_version__agent/workspace).order_by(-created_at)[:10]`; create validates `AgentModel.get(pk)`, `WorkspaceModel.get(pk)`, `SessionModel.filter(name).exists()` | Create session | `GET agents/`, `GET workspaces/`, `GET sessions/` (root filter client-side), `POST sessions/` — covered |

### 3.2 Sidebar (navigation — only workspaces subscribes, see §1.11)

| Component | File | Data needed | REST equivalent |
|---|---|---|---|
| `RailView`, `SidebarView`, `ProjectSelector` | `ui/sidebar/rail.py`, `sidebar.py:27-148`, `project_selector.py` | `selected_panel_name`, `url_params`, `selected_project_id`; `Project.objects.all()` for selector | `GET projects/` — covered |
| `SidebarPanelChats` + row | `ui/sidebar/panels/chats.py:78-512` | `_base_query:455-461` = `sessions.root().filter(parent_session__isnull, SESSION).select_related(latest_session_version__workspace).prefetch(child_sessions).filter(archived).order_by(-is_pinned, -created_at)` → `QuerySetView`; row: `messages.count()`, `latest_session_version.workspace.color/name`, `aimodel.name`; `mark_active:335-342` = `Query.filter(session_version__session, ACTIVE).exists() or AgentTaskCall.filter(session).exclude(ENDED).exists()`; `mark_needs_approval:345-352` = `AgentTaskCall.filter(session, requires_approval, HALTED_APPROVAL).exists()`; `visible_child_sessions:54-75` = `SessionModel.filter(parent_session, SESSION/SUBSESSION/SUBTASK_COMPACT/SUBTASK_DELEGATE)[+archived=False].filter(Q(active) \| last_active_at≥now-30m).select_related(latest_session_version__agent)` cap 5; `subagent_count: SessionModel.filter(parent_session__isnull=False, active, SESSION).count()`; refresh only via `refresh_list` on pin/archive/move/new (dead `_on_session_updated` never wired) | `GET sessions/` (+ client-side pin/archive/root/child filters), `GET queries?session=&status=ACTIVE`, `GET task-calls?session=` — mostly covered; **gaps: no `status_detail` filter, no `is_pinned`/`archived`/`parent_session` filters on `SessionViewSet` (`filterset_fields=name,is_active,is_archived`)** |
| `Agents / Cron / Collections / Workitems / Projects / Skills` panels | `ui/sidebar/panels/{agents,cron,collections,workitems,projects,skills}.py` | `AgentModel.root()/filter(parent_project)` + `aimodel/allowedSkills/Tools/Tasks/Commands`; `Cronjob.root().filter(archived)/filter(parent_project)` + `agent.name`; `DataCollection.all().order_by(name)` + `items.count()` + type display; `scoped_queryset(project_id)` + `status/title__icontains` + `count/active_count(in_review, blocked)`; `Project.root()`; `SkillModel.root()/filter(parent_project)` + client search filter | `GET agents/`, `GET cron/`, `GET collections/`, `GET projects/`, `GET skills/` — covered. **Workitems panel: no endpoint (see §1.10). Cron active/archived filter: check `CronViewSet`.** |
| `Insights/Settings/Logs` nav | `ui/sidebar/panels/{insights,settings,logs}.py` | Menu only; logs selects file/tail | Logs gap (see §2) |

### 3.3 Main tab views (only WorkItemsBoard subscribes, see §1.10)

| Component | File | Data needed | REST equivalent |
|---|---|---|---|
| `MainView` + `RightPanel` shell | `ui/main/main_view.py`, `ui/main/rightpanel/rightpanel.py` | `open_tabs{Class__uid:view}`, `RIGHTPANEL_VIEW` switch | Client-side routing — no REST |
| `AgentsOverview` / `AgentView` / create | `ui/main/agent/{overview,agent_view,create}.py` | Deep filtered counts: `SessionModel.filter(agent_filter)`, `Message/Response/AgentTaskCall/AgentTaskRun/Query.filter(deep_filter)` + `Response.filter(status=SUCCESS)`, incremental `pk__gt` polls; `defined_tools/tasks/commands/skills/subagents.select_related`, `SkillModelVersion.filter().select_related(skill)`, `AgentTaskCall` stats; `AiModel.all().order_by(name)`; **publishes** `AgentModel/update+delete (:796-809)` | `GET agents/`, `GET agents/{id}/{tools,tasks,commands,skills,subagents,versions}`, `GET sessions/?...`, `GET queries?`, `GET task-calls?`, `GET task-runs?` — mostly covered; **gap: no `responses` endpoint, no stats aggregate** |
| `Projects` overview/view/create | `ui/main/project/*.py` | `Agent/Session/Cronjob.filter(parent_project).count()`, `Project.all().order_by(-updated_at)`, `Project.filter(path).first()` | `GET projects/` (+ counts need 3 extra list calls or new counts field) |
| `Workspaces` overview/view/create/access | `ui/main/workspace/*.py` | `WorkspaceModel.all().order_by(name)`, `SessionVersionModel.filter(workspace)`, `SessionModel.filter(latest_session_version__workspace)`; **publishes** `WorkspaceModel create/update/delete` | `GET/POST/PATCH/DELETE workspaces/` — covered |
| `Cron` overview/view/create | `ui/main/cron/*.py` | `Cronjob.all().select_related(agent).order_by(-is_active, -last_run_at)`, `WorkspaceModel.all()`, `AgentModel.all()[visible]`, `SessionModel.filter(name__icontains).values_list(name).distinct()[:10]` | `GET cron/`, `GET agents/`, `GET workspaces/` — covered |
| `CollectionDetail / create` | `ui/main/collections/*.py` | `DataCollection.filter(active).exclude(pk)`, `CollectionItem.filter(collection).select_related(source_call).order_by(-pk)[:20]`, `AgentModel.all()`, `Project.all()`, `TaskDefinition.values_list(name)`, `SessionModel.values_list(name).distinct()[:50]` | `GET collections/`, `GET collections/{id}/items` (?) — check `CollectionViewSet` actions; **gap: no `CollectionItem` top-level filter, no `TaskDefinition` endpoint** |
| `SkillView` | `ui/main/skills/skill_view.py` | `versions.all().order_by(-version_number)` + frontmatter parse | `GET skills/{id}/versions` (check `SkillViewSet`) — likely covered |
| `Insights`: dashboard/analytics/providers/models | `ui/main/insights/{dashboard,analytics,providers,models}.py` | Counts: `Agent/Session/AgentTaskCall/DataCollection/Cronjob/Message.objects.count()`, `Response.aggregate(Sum prompt/completion/cached)`, `AgentTaskCall.values(status).annotate(Count)`, inspect `AgentTaskCall.select_related(...).order_by(-pk)[:200]` + `session_version__agent__name__icontains/status/task_definition__name__icontains/session__pk|name__icontains`; analytics: `Response.filter(status=SUCCESS)[+provider/model/date].aggregate(Count/Sum/Avg)`, `Trunc` buckets, scatter `[:800]`; `ApiProvider/ApiKey/AiModel` aggregates | **Gap: no stats/analytics endpoint.** Would need new `GET /insights/*` or client-side aggregation over existing lists (expensive) |
| `Logs / Memory` | `ui/main/logs/logs.py`, `ui/main/memory/memory.py` | Static shells filled by JS (`#logsOutput`, `#memoryDetailBody`) | **Gap: no logs/memory endpoint** |
| `Providers / Systems` | `ui/main/system/{providers,systems}.py` | `ApiProvider.all()` → children (`AiModel.create`, `ApiKey.create(key, comment, provider)`); `System.all()` | `GET providers/`, `GET models/`, `POST providers/{id}/...` (check), `GET systems/` — mostly covered; **gap: ApiKey CRUD unclear** |
| `Settings` + panels | `ui/main/settings/settings.py`, `panels/*.py` | `UiApp.settings` (`UserSettings`: theme/skin/font, send_key), `ApiProvider.filter(enabled)`, `ApiKey.get/create/delete` | `GET me/`, providers — partially; **gap: no user-settings endpoint** |

### 3.4 Right panel tabs (only session-templates subscribes, see §1.12)

| Component | File | Data needed | REST equivalent |
|---|---|---|---|
| Session tabs (workspace/settings/tasks/templates/todos/calls/subagents/terminal) | `ui/main/rightpanel/session/rightpanel_session*.py` | Calls: `AgentTaskCall.filter(session_root_task=root).select_related(...).order_by(-created_at)[:500]` tree via `parent_taskrun.agent_task_call_id`; active count excludes `ENDED`; settings: `CHOICE/INT/BOOLEAN_FIELDS` + `SessionModel.filter(pk).update(name)` (**publishes** `SessionModel/update :378-386`); subagents: `available_subagents ← allowedSubagentNames`, `SessionModel.filter(parent_session, is_active).order_by(-created_at)` + per-row `messages.count()`, `Query(ACTIVE)` / `AgentTaskCall(!ENDED)` / `HALTED_APPROVAL` checks; todos: `todolist_action` anchor (event-sourced, no DB); terminals: `list_terminals(subject)` (tmux) fallback `TerminalSession.filter(session).order_by(name)`, `log_path` tail 40 lines else `poll_output(lines=40)` | `GET task-calls?` (+ `task-runs?task_call=` for tree), `PATCH sessions/{id}`, `GET sessions/` (children), `POST sessions/{id}/call/...` — mostly covered; **gaps: no todos endpoint (event-sourced), no terminals endpoint** |
| Workspace/collection/agent/cron/project/provider/model/skill right panels | `ui/main/rightpanel/{workspace,collection,agent,cron,project,provider,model,skill}/*` | Subject fields + related `Session/TaskCall` counts; manual `refresh()` buttons; zero `orm_subscribe` | Same as §3.3 per-model endpoints |

## 4. API-coverage summary (what a new UI can use vs. must build)

### 4.1 Covered today (data fetch works, only push is missing)

- Sessions list/detail/create/rename/settings (`GET/POST/PATCH sessions/`, `POST reset`), session messages (`GET sessions/{id}/messages`, `POST sessions/{id}/message`), session tasks (`GET sessions/{id}/tasks`, `POST sessions/{id}/call/{name}`).
- Queries (`GET queries?session=&status=`, `GET queries/{id}`, `POST queries/{id}/cancel`).
- Task calls detail + approve/deny/answer (`GET task-calls/{id}`, `POST …/approve|deny|answer`); list filtered by `session` (but see 4.2).
- Agents + sub-resources (`GET agents/`, `…/{id}/{commands,tasks,tools,skills,subagents,versions}`).
- Workspaces / Projects / Collections / Cron / Skills / Providers / Models / Systems CRUD-or-read lists.

### 4.2 Partially covered (endpoint exists, filter/field missing)

| Need | Status |
|---|---|
| Queue / question / guardrail / rate-limit cards (`status_detail=WAITING_QUEUE / HALTED_APPROVAL / WAITING_RATELIMIT`) | `TaskCallFilter` has only `session,status,task_name` — **add `status_detail` (+ `status_detail__in`) filter** |
| Sidebar chat list (`is_pinned`, `archived`, `parent_session`, child sessions, `last_active_at`) | `SessionViewSet.filterset_fields=name,is_active,is_archived` — **add `is_pinned/archived/parent_session` filters + child include** |
| Approval card (`needs_approval`, turn counters) | Verify `SessionDetailSerializer` exposes them; if not, add |
| ToC compaction markers | Covered only if the API/`message_type` exposes compaction markers (`message_type=compaction`) — verify |
| Collection items / skill versions / provider keys | Verify nested routes exist (`collections/{id}/items`, `skills/{id}/versions`, ApiKey CRUD); add if missing |
| Project/agent overview counts | Work today via N list calls; consider `_counts` annotations or a stats action |

### 4.3 Not covered (new endpoints needed for a migrated UI)

| Need | Used by | Proposal |
|---|---|---|
| WorkItems CRUD + `?project=` + `?parent=` + children/counts | Board (§1.10), sidebar workitems panel | New `WorkItemViewSet` (`GET/POST/PATCH/DELETE workitems/`) + publish on write (already publishes via `workitem_fsm.py:76`) |
| Context usage (`used_context_percent/tokens`, max, send/received/cached) | `CtxIndicatorWrap` (§1.8) | New `GET sessions/{id}/usage` (wraps `Session.context_usage()`) |
| Terminals (list/output/kill) | `TerminalPanel`, session-terminal tab | New `GET/POST/DELETE sessions/{id}/terminals` (wraps `list_terminals` / `poll_output`) |
| Logs (file list + tail) | Logs panel + main logs view (§2) | New `GET /logs?file=&tail=` (or document the ad-hoc fetch URL the JS uses today) |
| Insights/analytics aggregates | Dashboard, analytics, providers/models insights | New `GET /insights/{dashboard,analytics,costs}` (counts + `Response` aggregates), or accept client-side aggregation |
| Responses / token stats | Agent overview, analytics | New read-only `ResponseViewSet` or fold into insights endpoint |
| Todos (event-sourced `todolist_action`) | Session-todos tab | New `GET sessions/{id}/todos` (wraps the anchor's `latest_result()`) |
| User settings (theme/skin/send_key/…) | Composer box, settings panels | New `GET/PATCH /me/settings` or settings viewset |
| `ask_user` pending-question shaping | Question card | Could stay client-side over `GET task-calls?` once `status_detail` filter exists |
| Push channel | All §1 rows | Either poll (intervals: 2s rate-limit, ~5s chat, ~10s board/sidebar) or add websocket/SSE emitting `(key, model, pk, action)` like `process_queue_messages` does today (`ui/consumer.py:25`). Without it, every §1 row becomes a poller |

## 5. File index (where to look when building the new UI)

- Transport: `runtime/observables.py:55 subscribe`, `:88 notify`; `runtime/events.py:47 publish_model_event`; `server/models/base_model.py:55-105 ObservableMixin`.
- Consumer: `ui/consumer.py:25 process_queue_messages`, `:55 loop`, `:91 _ensure_loop_thread`; `ui/lib/model_view.py:17 orm_subscribe`, `:40 orm_unsubscribe_view`.
- Live views: `ui/main/chat/messages/messages.py`, `ui/main/chat/composer/footer.py`, `ui/main/chat/composer/wrap/ctxindicator.py`, `ui/main/chat/toc.py`, `ui/main/chat/cards/{approval,queue,question,guardrail_approval,rate_limit}.py`, `ui/main/workitems/board.py`, `ui/sidebar/panels/workspaces.py`, `ui/main/rightpanel/session/rightpanel_session_templates.py`.
- API: `api/urls.py`, `api/views/{sessions,queries,tasks,agents,workspaces,collections,cron,providers,skills,projects,systems}.py`, `api/serializers/`.
- Tests pinning behavior: `server/tests/test_observables.py`, `test_messages_ui.py`, `test_workitem_ui.py`, `test_rate_limit_card.py`, `test_workspaces_ui.py`, `api/tests/test_{workspaces,tasks,ask_user,deny_feedback}.py`.
