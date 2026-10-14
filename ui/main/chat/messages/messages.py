from __future__ import annotations
import threading
from typing import TYPE_CHECKING
from runtime.session.session import Session
from server.models.enums.message_enums import MessageRole
from server.models.message import Message
from server.models.queries.query import Query
from server.models.queries.response import Response
from ui.lib.pyHtmlGui.pyhtmlgui.lib.observableList import ObservableList
from ui.lib.pyHtmlGui.pyhtmlgui.view.observable_list_view import ObservableListView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.main.chat.messages.message import MessageView
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.chat.chat import Chat


class ObservableMessageListView(ObservableListView):
    TEMPLATE_STR = '''
        {% for item in pyview.get_items() %}
            {{ item.render() }}
        {% endfor %}
       
    '''
class Messages(PyHtmlView):
    DOM_ELEMENT_CLASS = 'messages'
    TEMPLATE_STR = '''
    <style>

@keyframes smoothAppear {
  0% {
    opacity: 0;
    transform: translateY(50%);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}
    </style>
            <button id="scrollToBottomBtn" class="scroll-to-bottom-btn" aria-label="Scroll to bottom" onclick="var e=document.getElementById('{{pyview.uid}}');if(e)e.scrollTop=e.scrollHeight;pyview.scrollToBottom()">↓</button>

            <div class="empty-state" id="emptyState" style="display:none">
                <div class="empty-logo"></div>
                <h2 data-i18n="empty_title">What can I help with?</h2>
                <p data-i18n="empty_subtitle">Ask anything, run commands, explore files, or manage your scheduled tasks.</p>
            </div>
            
            <div id="top-sentinel" style="height: 1px;position:relative;top:"></div>
            {{ pyview.messages_view.render() }}
            <div id="bottom-sentinel" style="height: 1px;"></div>    
            <div id="liveCompressionCards" class="live-compression-cards"></div>

            <div id="liveToolCards" style="display:none1;max-width:800px;margin:0 auto;width:100%;padding:0 24px;"></div>

            
            <script>

                 options = {
                    rootMargin: '5% 0px 5% 0px',
                    threshold: 0
                 };

                 var observer = new IntersectionObserver((entries) => {
                    entries.forEach(entry => {
                        if (!entry.isIntersecting) return;
                        if (entry.target.id === 'top-sentinel') {
                            var el = document.getElementById('{{pyview.uid}}');
                            var pct = el ? Math.round(el.clientHeight * 0.05) : 1;
                            if (el && el.scrollTop < pct) {
                                el.scrollTop = pct * 1.05;
                                pyview.up();
                            }
                            
                        } else if (entry.target.id === 'bottom-sentinel') {
                            pyview.down();
                        }
                    });
                 }, options);

                 observer.observe(document.getElementById('top-sentinel'));
                 observer.observe(document.getElementById('bottom-sentinel'));

                 var e=document.getElementById('{{pyview.uid}}');
                 if(e){
                    e.scrollTop=e.scrollHeight;
                 }
            </script>

    '''

    def __init__(self, subject: Session, parent: Chat, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.max_visible_items = 100
        # Turn collapsing: per user-message block, only the latest
        # ``tail_turns`` agent turns stay expanded; older finished turns
        # hide entirely and the first visible turn of the block renders one
        # "N assistant messages hidden (show)" line. Clicking it pins the
        # block expanded (click again to collapse back).
        self.tail_turns = 2
        self._turn_auto: dict[int, bool] = {}
        self._turn_queries: dict[int, list[int]] = {}
        self._turn_block: dict[int, int | None] = {}
        self._turn_hidden: dict[int, int] = {}
        self._block_pin: dict[int | None, bool] = {}
        self._turn_applied: dict[tuple[str, int], tuple] = {}

        self._session_id = subject.model.pk
        # Redis observable path (replaces the ModelObserver watches): the
        # session-scoped keys are exactly what notify_observers() publishes
        # for these models' writes (dual-published from publish_model_event).
        # Subscriptions are per UI instance, so no unwatch_filter clearing
        # of stale/other views' subscriptions is needed.
        try:
            from ui.lib.model_view import orm_subscribe

            for _key in (
                f"Message.session:{self._session_id}",
                f"Query.session:{self._session_id}",
                f"Response.session:{self._session_id}",
                f"AgentTaskCall.session:{self._session_id}",
            ):
                orm_subscribe(self, _key, self._on_orm_event)
        except Exception:
            pass

        self.message_list = ObservableList()

        self.load_message_from_bottom()
        
        self.messages_view = ObservableListView(
            subject=self.message_list, 
            parent=self, 
            item_class=MessageView,
            dom_element_class="messages-inner",
        )

    def jump_to_message(self, message_pk: int) -> None:
        """Load a window of messages ending at ``message_pk`` and scroll its
        row to the top of the viewport.

        Used by the chat table-of-contents to jump to a compaction boundary
        that may be far outside the currently loaded window.
        """
        from server.models.message import Message as Msg
        target = Msg.objects.filter(pk=message_pk, session__pk=self._session_id).first()
        if target is None:
            return
        messages = []
        current = target
        while current and len(messages) < self.max_visible_items:
            messages.append(current)
            current = current.prev_message
        messages.reverse()
        with self._callback_lock:
            self.message_list.clear()
            for message in messages:
                self.message_list.append(message)
                for query in message.related_queries.filter(session_version__session=self.subject.model).order_by("-pk"):
                    self.message_list.append(query)
        self._refresh_turns()
        self._scroll_to_row(message_pk)

    def _scroll_to_row(self, message_pk: int) -> None:
        try:
            self._instance.call_javascript(
                "pyhtmlgui.eval_script",
                ["var c=document.getElementById('{}');var r=c&&c.querySelector('[data-pk=\"{}\"]');if(c&&r)c.scrollTop=r.getBoundingClientRect().top-c.getBoundingClientRect().top+c.scrollTop-16;".format(self.uid, message_pk), {}],
                skip_results=True,
            )
        except Exception:
            pass

    def load_message_from_bottom(self):
        tail = self.subject.get_last_message()
        if self.message_list and tail == self.message_list[-1]:
            return
        messages = []
        current = tail
        while current and len(messages) < self.max_visible_items:
            messages.append(current)
            current = current.prev_message
        messages.reverse()
        with self._callback_lock:
            self.message_list.clear()
            for message in messages:
                self.message_list.append(message)
                for query in message.related_queries.filter(session_version__session=self.subject.model).order_by("-pk"):
                    self.message_list.append(query)
        # Warm the turn maps so wrappers created on first render pick up
        # their collapse state in __init__.
        self._refresh_turns()


    def _log(self, msg: str) -> None:
        try:
            with open("/tmp/agentone_events.log", "a") as _f:
                import time
                _f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        except Exception:
            pass

    def scrollToBottom(self) -> None:
        self.load_message_from_bottom()
        try:
            self._instance.call_javascript(
                "pyhtmlgui.eval_script",
                ["document.getElementById('{}').scrollTop=document.getElementById('{}').scrollHeight".format(self.uid, self.uid), {}],
                skip_results=True,
            )
        except Exception:
            pass

    def _auto_scroll_if_needed(self) -> None:
        try:
            self._instance.call_javascript(
                "pyhtmlgui.eval_script",
                ["var el=document.getElementById('{}');if(el&&el.scrollHeight-el.clientHeight-el.scrollTop<150)el.scrollTop=el.scrollHeight;".format(self.uid), {}],
                skip_results=True,
            )
        except Exception:
            pass

    _callback_lock = threading.Lock()

    def _on_orm_event(self, key=None, model=None, pk=None, action=None, data=None) -> None:
        """Redis observable callback: route to the matching chat-log handler."""
        try:
            if model == "Message" and action == "create":
                self._on_message_created(pk, action, {})
            elif model == "Query" and action == "create":
                self._on_query_created(pk, action, {})
            elif model == "Query" and action == "update":
                self._on_query_updated(pk, action, {})
            elif model == "Response" and action in ("create", "update"):
                self._on_response_updated(pk, action, {})
            elif model == "AgentTaskCall" and action == "update":
                self._on_taskcall_updated(pk, action, {})
        except Exception:
            pass

    def _on_message_created(self, pk: int, action: str, filter_context: dict) -> None:
        from server.models.message import Message as Msg
        import traceback
        stack = ''.join(traceback.format_stack()[-5:-1])
        self._log(f"Messages._on_message_created: pk={pk} action={action} uid={id(self)} listlen={len(self.message_list)} fc={filter_context}\n{stack}")
        with self._callback_lock:
            try:
                msg = Msg.objects.get(pk=pk)
            except Msg.DoesNotExist:
                self._log(f"Messages._on_message_created: Msg {pk} DoesNotExist")
                return
            existing = [item for item in self.message_list if isinstance(item, Msg) and item.pk == pk]
            if existing:
                self._log(f"Messages._on_message_created: {pk} already in list, skipping (found {len(existing)} existing)")
                return

            prev_id = (filter_context or {}).get("prev_message_id")
            if prev_id is None:
                prev_id = getattr(msg, "prev_message_id", None)
            inserted = False
            if prev_id is not None:
                for idx, item in enumerate(self.message_list):
                    if isinstance(item, Msg) and item.pk == prev_id:
                        self._log(f"Messages._on_message_created: inserting {pk} after msg {prev_id} at index {idx+1}")
                        self.message_list.insert(idx + 1, msg)
                        inserted = True
                        break
            if not inserted:
                self._log(f"Messages._on_message_created: appending {pk} (list had {len(self.message_list)} items)")
                self.message_list.append(msg)

            if hasattr(msg, "related_queries"):
                for query in msg.related_queries.all().order_by("-pk"):
                    if not any(isinstance(item, Query) and item.pk == query.pk for item in self.message_list):
                        self.message_list.append(query)
            self._auto_scroll_if_needed()
            self._refresh_turns()

    def _on_query_created(self, pk: int, action: str, filter_context: dict) -> None:
        from server.models.queries.query import Query as QueryModel
        with self._callback_lock:
            try:
                query = QueryModel.objects.get(pk=pk)
            except QueryModel.DoesNotExist:
                return
            trigger_msg_pk = (filter_context or {}).get("trigger_message_id")
            if trigger_msg_pk is None:
                trigger_msg_pk = getattr(query, "trigger_message_id", None)
            if trigger_msg_pk is None:
                return
            if any(isinstance(item, Query) and item.pk == pk for item in self.message_list):
                self._log(f"_on_query_created: Query {pk} already in list, skipping")
                return
            for idx, item in enumerate(self.message_list):
                if isinstance(item, Message) and item.pk == trigger_msg_pk:
                    self._log(f"_on_query_created: inserting Query {pk} after msg {trigger_msg_pk} at index {idx+1}")
                    self.message_list.insert(idx + 1, query)
                    self._auto_scroll_if_needed()
                    self._refresh_turns()
                    return

    def _on_query_updated(self, pk: int, action: str, filter_context: dict) -> None:
        self._log(f"_on_query_updated: pk={pk} action={action} fc={filter_context}")
        for wrapper in self.messages_view._wrapped_data:
            subj = wrapper.subject
            if subj is None:
                continue
            if isinstance(subj, Query) and subj.pk == pk:
                if hasattr(wrapper, 'view'):
                    self._log(f"_on_query_updated: found wrapper for Query {pk}, calling view.update()")
                    try:
                        subj.refresh_from_db()
                    except Exception:
                        pass
                    wrapper.view.update()
                    self._refresh_turns()
                return
        self._log(f"_on_query_updated: no wrapper found for Query {pk} in _wrapped_data (len={len(self.messages_view._wrapped_data)})")

    def _on_taskcall_updated(self, pk: int, action: str, filter_context: dict) -> None:
        self._log(f"_on_taskcall_updated: pk={pk} action={action} fc={filter_context}")
        for wrapper in self.messages_view._wrapped_data:
            if wrapper.subject is None:
                continue
            if not isinstance(wrapper.subject, Message):
                continue
            msg_view = getattr(wrapper, 'view', None)
            if msg_view is None:
                continue
            tool_list = getattr(msg_view, 'tool_list', None)
            if tool_list is None:
                continue
            for tool_card in tool_list._wrapped_data:
                if getattr(tool_card.subject, 'pk', None) == pk:
                    self._log(f"_on_taskcall_updated: found ToolCard for call {pk}, calling update()")
                    try:
                        tool_card.subject.refresh_from_db()
                    except Exception:
                        pass
                    tool_card.update()
                    return
        self._log(f"_on_taskcall_updated: no ToolCard found for call {pk}")

    def _turn_effective(self, assistant_pk: int | None) -> bool:
        """Effective collapse state: a pinned block stays fully expanded."""
        if assistant_pk is None:
            return False
        if self._block_pin.get(self._turn_block.get(assistant_pk)):
            return False
        return self._turn_auto.get(assistant_pk, False)

    def toggle_block(self, assistant_pk: int | None) -> None:
        """Expand a block's hidden turns, or collapse back to auto."""
        if assistant_pk is None:
            return
        bkey = self._turn_block.get(assistant_pk)
        if bkey in self._block_pin:
            del self._block_pin[bkey]
        else:
            self._block_pin[bkey] = True
        self._refresh_turns()

    def _turn_is_live(self, assistant_item: Message | None, query_items: list[Query],
                      query_statuses: dict | None = None,
                      response_statuses: dict | None = None) -> bool:
        """Whether a turn is still working (never auto-collapsed).

        Statuses come from the freshly read maps (falling back to the
        in-memory objects): the items in ``message_list`` go stale as soon
        as later saves flip rows that no event re-fetches.
        """
        query_statuses = query_statuses or {}
        response_statuses = response_statuses or {}
        try:
            for query in query_items:
                qpk = getattr(query, "pk", None)
                status = query_statuses.get(qpk, getattr(query, "status", "") or "")
                if (status or "") == "ACTIVE":
                    return True
        except Exception:
            pass
        if assistant_item is None:
            return True
        try:
            rid = getattr(assistant_item, "response_id", None)
            if rid is None:
                return True
            if rid in response_statuses:
                return (response_statuses[rid] or "").upper() == "ACTIVE"
            resp = getattr(assistant_item, "response", None)
            if resp is None or getattr(resp, "pk", None) is None:
                return True
            if (getattr(resp, "status", "") or "").upper() == "ACTIVE":
                return True
        except Exception:
            return True
        return False

    def _turn_has_approval(self, assistant_item: Message) -> bool:
        """Whether a turn waits on a tool approval (never auto-collapsed)."""
        try:
            from server.models.tasks.agent_task_call import AgentTaskCall
            call_ids = [
                part.tool_call_id
                for part in assistant_item.parts.filter(tool_call__isnull=False)
                if getattr(part, "tool_call_id", None)
            ]
            if not call_ids:
                return False
            return AgentTaskCall.objects.filter(
                pk__in=call_ids, status_detail="HALTED_APPROVAL"
            ).exists()
        except Exception:
            return False

    def _refresh_turns(self) -> None:
        """Recompute turn grouping + auto-collapse for the visible window.

        A turn is one assistant message plus the query cards that produced
        it; turns are grouped per user-message block (keyed by the block's
        user message pk, so pins survive window paging). Only the latest
        ``tail_turns`` finished turns per block stay expanded — older ones
        hide entirely and the block's first visible turn renders one "N
        assistant messages hidden (show)" line. A pinned block stays fully
        expanded. Views update only on change.
        """
        try:
            items = list(self.message_list)
        except Exception:
            return
        # Segment into turns: (block_key, assistant Message|None, [Query]).
        # Queries listed before an assistant message produced it; trailing
        # queries with no assistant yet form an open (always live) turn.
        turns: list[tuple[int | None, Message | None, list[Query]]] = []
        block_key: int | None = None
        pending: list[Query] = []
        for item in items:
            try:
                if isinstance(item, Message) and item.role == MessageRole.USER:
                    if pending:
                        if turns and turns[-1][0] == block_key and turns[-1][1] is not None:
                            turns[-1][2].extend(pending)
                        else:
                            turns.append((block_key, None, list(pending)))
                        pending = []
                    try:
                        block_key = item.pk
                    except Exception:
                        block_key = None
                elif isinstance(item, Query):
                    pending.append(item)
                elif isinstance(item, Message) and item.role == MessageRole.ASSISTANT:
                    turns.append((block_key, item, list(pending)))
                    pending = []
            except Exception:
                continue
        if pending:
            turns.append((block_key, None, list(pending)))

        # Fresh statuses: list items go stale while later saves flip rows.
        query_statuses: dict = {}
        response_statuses: dict = {}
        try:
            qpks = [q.pk for _, _, qs in turns for q in qs if getattr(q, "pk", None) is not None]
            if qpks:
                query_statuses = dict(
                    Query.objects.filter(pk__in=qpks).values_list("pk", "status")
                )
        except Exception:
            query_statuses = {}
        try:
            rids = [
                a.response_id for _, a, _ in turns
                if a is not None and getattr(a, "response_id", None) is not None
            ]
            if rids:
                response_statuses = dict(
                    Response.objects.filter(pk__in=rids).values_list("pk", "status")
                )
        except Exception:
            response_statuses = {}

        auto: dict[int, bool] = {}
        queries_of: dict[int, list[int]] = {}
        block_of: dict[int, int | None] = {}
        dangling_qpks: list[int] = []
        # Assistant pks per block, in order (for tail + hidden counts).
        per_block: dict[int | None, list[int]] = {}
        for _bkey, assistant_item, _qs in turns:
            if assistant_item is not None:
                try:
                    per_block.setdefault(_bkey, []).append(assistant_item.pk)
                except Exception:
                    continue
        for _bkey, assistant_item, query_items in turns:
            try:
                qpks = [q.pk for q in query_items if getattr(q, "pk", None) is not None]
            except Exception:
                qpks = []
            if assistant_item is None:
                dangling_qpks.extend(qpks)
                continue
            try:
                apk = assistant_item.pk
            except Exception:
                continue
            queries_of[apk] = qpks
            block_of[apk] = _bkey
            block_pks = per_block.get(_bkey, [])
            try:
                idx = block_pks.index(apk) + 1
            except ValueError:
                idx = 1
            total = len(block_pks)
            in_tail = idx > max(total - self.tail_turns, 0)
            collapsed = not in_tail and not self._turn_is_live(
                assistant_item, query_items, query_statuses, response_statuses
            )
            if collapsed and self._turn_has_approval(assistant_item):
                collapsed = False
            auto[apk] = collapsed
        self._turn_auto = auto
        self._turn_queries = queries_of
        self._turn_block = block_of
        for apk in auto:
            self._apply_turn(apk)
        # Hidden counts: each block's first visible turn carries the line.
        hidden: dict[int, int] = {}
        for _bkey, block_pks in per_block.items():
            try:
                collapsed_pks = [pk for pk in block_pks if self._turn_effective(pk)]
            except Exception:
                collapsed_pks = []
            first_visible = next((pk for pk in block_pks if not self._turn_effective(pk)), None)
            if first_visible is not None:
                hidden[first_visible] = len(collapsed_pks)
        self._turn_hidden = hidden
        for apk in auto:
            self._apply_turn(apk)
        # Dangling (still streaming) queries always stay visible.
        try:
            wrappers = list(self.messages_view._wrapped_data)
        except Exception:
            return
        for wrapper in wrappers:
            try:
                subj = getattr(wrapper, "subject", None)
                if isinstance(subj, Query) and subj.pk in dangling_qpks:
                    qview = getattr(wrapper, "view", None)
                    if qview is not None and getattr(qview, "turn_collapsed", False):
                        qview.turn_collapsed = False
                        wrapper.update()
            except Exception:
                continue

    def _apply_turn(self, assistant_pk: int) -> None:
        """Push the effective (manual over auto) collapse state to views."""
        effective = bool(self._turn_effective(assistant_pk))
        hidden = int(self._turn_hidden.get(assistant_pk, 0) or 0)
        bkey = self._turn_block.get(assistant_pk)
        pinned = bool(self._block_pin.get(bkey, False))
        qpks = self._turn_queries.get(assistant_pk, [])
        try:
            wrappers = list(self.messages_view._wrapped_data)
        except Exception:
            return
        for wrapper in wrappers:
            try:
                subj = getattr(wrapper, "subject", None)
                if subj is None:
                    continue
                if isinstance(subj, Message) and subj.pk == assistant_pk:
                    view = getattr(wrapper, "view", None)
                    if view is None or not hasattr(view, "turn_collapsed"):
                        continue
                    sig = (effective, hidden, pinned)
                    if self._turn_applied.get(("msg", assistant_pk)) == sig and getattr(view, "turn_collapsed", False) == effective:
                        continue
                    view.turn_collapsed = effective
                    view.hidden_count = hidden
                    view.block_pinned = pinned
                    self._turn_applied[("msg", assistant_pk)] = sig
                    # Update the wrapper (not just the inner view): the row's
                    # display:none/display:flex lives in its extras.
                    wrapper.update()
                elif isinstance(subj, Query) and subj.pk in qpks:
                    qview = getattr(wrapper, "view", None)
                    if qview is None:
                        continue
                    if getattr(qview, "turn_collapsed", False) != effective:
                        qview.turn_collapsed = effective
                        wrapper.update()
            except Exception:
                continue

    def _on_response_updated(self, pk: int, action: str, filter_context: dict) -> None:
        """Refresh the query + assistant views owning a Response.

        Interim ACTIVE streaming saves are skipped (nothing visible
        changes); terminal saves refresh the owning views and recompute
        turns.
        """
        try:
            resp = Response.objects.get(pk=pk)
        except Response.DoesNotExist:
            return
        except Exception:
            return
        terminal = (getattr(resp, "status", "") or "").upper() in ("SUCCESS", "FAILURE")
        if not terminal:
            return
        try:
            wrappers = list(self.messages_view._wrapped_data)
        except Exception:
            return
        for wrapper in wrappers:
            try:
                subj = getattr(wrapper, "subject", None)
                if subj is None:
                    continue
                if isinstance(subj, Query) and subj.pk == getattr(resp, "query_id", None):
                    try:
                        subj.refresh_from_db()
                    except Exception:
                        pass
                    try:
                        wrapper.view.update()
                    except Exception:
                        pass
                elif isinstance(subj, Message) and getattr(subj, "response_id", None) == pk:
                    try:
                        subj.refresh_from_db()
                        related = getattr(subj, "response", None)
                        if related is not None:
                            related.refresh_from_db()
                    except Exception:
                        pass
                    try:
                        wrapper.view.update()
                    except Exception:
                        pass
            except Exception:
                continue
        self._refresh_turns()

    def _first_message(self):
        for item in self.message_list:
            if isinstance(item, Message):
                return item
        return None

    def _last_message(self):
        for item in reversed(self.message_list):
            if isinstance(item, Message):
                return item
        return None

    def _message_count(self) -> int:
        return sum(1 for item in self.message_list if isinstance(item, Message))

    def up(self):
        first = self._first_message()
        if not first:
            return

        for _ in range(self.max_visible_items//4):
            older = first.prev_message
            if older is None:
                break
            self.message_list.insert(0, older)
            for query in older.related_queries.filter(session_version__session=self.subject.model).order_by("-pk"):
                self.message_list.insert(1, query)
            first = older

        delcnt = self._message_count() - self.max_visible_items
        if delcnt > 0:
            for _ in range(delcnt):
                del self.message_list[-1]
        self._refresh_turns()

    def down(self):
        last = self._last_message()
        if not last:
            return

        for _ in range(self.max_visible_items//4):
            newer = last.next_messages.filter(session_version__session=self.subject.model).first()
            if newer is None:
                # Window was scrolled up across a fork into another session's
                # chain (up() follows prev_message unfiltered). The foreign
                # chain is linear here, so walk it back toward the fork;
                # at the fork itself the filtered lookup above already hits.
                newer = last.next_messages.order_by("pk").first()
            if newer is None:
                break
            self.message_list.append(newer)
            for query in newer.related_queries.filter(session_version__session=self.subject.model).order_by("pk"):
                self.message_list.append(query)
            last = newer

        delcnt = self._message_count() - self.max_visible_items
        if delcnt > 0:
            for _ in range(delcnt):
                del self.message_list[0]
        self._refresh_turns()
        