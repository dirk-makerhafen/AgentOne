# Observables migration — current state

> **Status: implemented.** ORM→UI updates flow exclusively through the
> Redis observable registry (`runtime/observables.py`). The Channels-group
> path is fully removed (`publish()` / `CHANNEL_GROUP`,
> `PyHtmlGuiConsumer.session_event`, consumer group membership, and
> `UiApp.dispatch_session_event` are all gone); `ui/model_observer.py`
> is retired but kept as an unwired fallback reference.

## How it works now

| Stage | Mechanism |
|---|---|
| Producer | `publish_model_event(instance, action)` (`runtime/events.py:73`) calls `instance.notify_observers(action)` — one choke point for all ~35 existing call sites (Celery tasks, `.agentone/scripts/`, `runtime/`, `api/`, `ui/`), including `QuerySet.update()` flows that bypass `save()`. Instances without `notify_observers` are skipped via `getattr`. |
| Transport | `runtime.observables.notify()` (`runtime/observables.py:88`) `HGETALL`s each key's observers and `RPUSH`es **one message per subscribed UI instance** to `agentone:uiq:<instance_key>`. Observer-gated: instances with no subscription for the affected keys get nothing. |
| Keys | `ObservableMixin.observable_keys()` (`server/models/base_model.py:75`): the `any` key (`<Model>`), the `pk` key (`<Model>.pk:<pk>`), plus one key per set FK (`<Model>.<field>:<id>`). Per-model `<Model>Observables` helpers expose the same strings for subscribers (e.g. `project.observables.child_agents` → `AgentModel.parent_project:<pk>`). The mixin (not `BaseModel`) owns `.observables` / `observable_keys()` / `notify_observers()` (`base_model.py:55-105`), so **every** ORM model is observable — including the plain-`models.Model` ones (`WorkspaceModel`, `GenericContent`, `SkillModelVersion`, `Project`, `SkillModel`), which all mix it in. Auto-created M2M through-models are the only exception. Covered by `AllModelsObservableTest`, which asserts the capability on every concrete `server` model. |
| Consumer | One drain thread per UI instance (`ui/consumer.py:54`, started via `_ensure_loop_thread`, `ui/consumer.py:83`). `BLPOP timeout=5` + full-list drain so bursts coalesce; the thread exits once its instance has no connections. `process_queue_messages` (`ui/consumer.py:24`) invokes one callback per `function_id` (latest message wins), resolving through the instance's `_function_references` (weak — GC'd views are skipped). |
| Subscription | `orm_subscribe(view, key, target)` / `orm_unsubscribe_view(view, key?)` (`ui/lib/model_view.py:17,40`) — usable from any view; tracked on `view._observed_function_ids` and `instance.observed_views`. `ModelView.add_observable` delegates to `orm_subscribe`; `ModelView.__init__` auto-subscribes only when the subject is an ORM instance (has `.observables`). |

Why this is faster than what it replaced: the old path broadcast **every**
model event to **every** connected consumer through the channel layer, then
re-matched filters in-process. The registry pushes only to subscribed
instance queues, batches one message per instance, and the loop coalesces
repeats per `function_id` before invoking anything.

## Subscribers (all converted)

Each old `watch(model, filter, action)` became a key subscription plus an
`_on_orm_event(key, model, pk, action, data)` router. `Message`, `Query`
and `AgentTaskCall` all have direct `session` FKs, so
`{"session_id": X}` filters mapped 1:1 to `"<Model>.session:X"` keys:

| View | Keys | Router behavior |
|---|---|---|
| chat `Messages` (`ui/main/chat/messages/messages.py`) | `Message`/`Query`/`AgentTaskCall.session:<sid>` | routes create/update to `_on_message_created` / `_on_query_created` / `_on_query_updated` / `_on_taskcall_updated`; the first two fall back to `msg.prev_message_id` / `query.trigger_message_id` from the re-fetched object instead of `filter_context` |
| composer footer (`ui/main/chat/composer/footer.py`) | same 3 keys | `_on_activity_event` (re-renders only when busy/mode state flipped) |
| ctxindicator (`ui/main/chat/composer/wrap/ctxindicator.py`) | `Query.session:<sid>` | refresh on `update` (old watch had an empty filter + in-callback session check; the session key delivers exactly the relevant subset) |
| chat toc (`ui/main/chat/toc.py`) | `Message.session:<sid>` | rebuild segments on compaction-message `create` |
| question / guardrail / rate-limit cards (`ui/main/chat/cards/`) | `AgentTaskCall.session:<sid>` | `update()` on task-call `update` |
| approval card (`ui/main/chat/cards/approval.py`) | `SessionModel.pk:<sid>` | `update()` on session `update` (renders `needs_approval()` from the turn counters) |
| queue card (`ui/main/chat/cards/queue.py`) | `AgentTaskCall.session:<sid>` | `update()` + pill sync on task-call create/update/delete |
| workitems board (`ui/main/workitems/board.py`) | `WorkItem` (any-key) | clear caches + `update()` |
| workspaces sidebar (`ui/sidebar/panels/workspaces.py`) | `WorkspaceModel` (any-key) | `update()` |

`LiveSession` (`ui/live.py`, retired): the four cards used to hold
in-process subscriptions to it, but nothing ever notified it — the only
notifier fed off channel events that had no producers. Replaced by the DB
subscriptions above, then deleted along with `UiApp.get_live_session` and
`Chat.live_session`. Missing producers were added too:
`Session.count_turn()` / `count_unattended_turn()`
(`runtime/session/session.py`) now `publish_model_event(session, "update")`
after the counter write (same pattern as `set_is_active`) and sync the
in-memory copy, so the approval card appears exactly when the limit is hit.

## Tests

- `server/tests/test_observables.py` (24 tests): registry subscribe/notify/
  unsubscribe against fakeredis (incl. multi-key merge → `keys` list),
  key-helper formats, `notify_observers` end-to-end (subscribe → notify →
  queue payload), dual-publish via `publish_model_event`, `orm_subscribe`
  bookkeeping, `process_queue_messages` coalescing + dead-weakref skip,
  plus `AllModelsObservableTest` (every concrete `server` model exposes
  `.observables` / `observable_keys()` / `notify_observers()`) and
  instance-level tests for the non-`BaseModel` mixins.
- `server/tests/test_workitem_ui.py`: board observer tests rewritten for
  redis (register → redis hash, re-init stays at 1 fid, `_on_orm_event`
  clears caches + re-renders).
- `server/tests/test_messages_ui.py`: fakeredis end-to-end
  (notify → queue → router → message-list insert).
- `server/tests/test_rate_limit_card.py`: approval/queue card router tests
  (session/task-call key → `update`, pill sync crash-safe) plus
  `SessionCounterPublishTest` (`count_turn` / `count_unattended_turn`
  publish + increment).
- Full `server/tests/` suite: no new failures vs the pre-migration
  baseline (46 pre-existing failures + 1 wall-clock flake in
  `test_pick_excludes_throttled_provider`, verified identical via
  `git stash` before/after runs).

## Remaining / known limitations

- Queued messages carry `keys` (all matched keys) alongside `key` (first
  match, kept for compatibility).

## File index

- `runtime/observables.py` (135 lines) — `get_redis:47`, `subscribe:55`,
  `unsubscribe:66`, `unsubscribe_all:80`, `notify:88`
- `server/models/base_model.py` — `Observables:15`, `ObservableMixin:55`
  (`.observables:67`, `observable_keys:75`, `notify_observers:93`),
  `BaseModel:109`
- `runtime/events.py` — `publish_model_event` (redis notify only),
  `_extract_filter_context` (kept for logging/tests)
- `ui/lib/model_view.py` — `orm_subscribe:17`,
  `orm_unsubscribe_view:40`, `ModelView` (`__init__:63`,
  `add_observable:114`, `remove_observable:122`)
- `ui/consumer.py` — `process_queue_messages:24`, `loop:54`,
  `_ensure_loop_thread:83`, per-consumer `self._instance`
  (`connect` / `disconnect`); no channel-layer code remains
- `ui/app.py` — `dispatch_session_event`, `_live_sessions`,
  `get_live_session` removed
- `ui/main/chat/chat.py` — `live_session` removed; cards subscribe to DB keys
- `ui/model_observer.py` — retired subscriber registry (unwired, kept)
