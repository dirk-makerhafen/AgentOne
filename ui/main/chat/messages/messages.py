from __future__ import annotations
import threading
from typing import TYPE_CHECKING
from runtime.session.session import Session
from server.models.message import Message
from server.models.queries.query import Query
from server.models.tasks.agent_task_call import AgentTaskCall
from ui.lib.pyHtmlGui.pyhtmlgui.lib.observableList import ObservableList
from ui.lib.pyHtmlGui.pyhtmlgui.view.observable_list_view import ObservableListView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.main.chat.messages.message import MessageView
from ui.lib.model_view import ModelView
from ui.app import UiApp

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
        
        self._session_id = subject.model.pk
        app = UiApp.get_instance()
        if app is not None:
            app.model_observer.unwatch_filter(
                model_class=Message,
                filter={"session_id": self._session_id},
            )
            app.model_observer.unwatch_filter(
                model_class=Query,
                filter={"session_id": self._session_id},
            )
            app.model_observer.watch(
                Message,
                filter={"session_id": self._session_id},
                callback_name="_on_message_created",
                view=self,
                action="create",
            )
            app.model_observer.watch(
                Query,
                filter={"session_id": self._session_id},
                callback_name="_on_query_created",
                view=self,
                action="create",
            )
            app.model_observer.watch(
                Query,
                filter={"session_id": self._session_id},
                callback_name="_on_query_updated",
                view=self,
                action="update",
            )
            app.model_observer.unwatch_filter(
                model_class=AgentTaskCall,
                filter={"session_id": self._session_id},
            )
            app.model_observer.watch(
                AgentTaskCall,
                filter={"session_id": self._session_id},
                callback_name="_on_taskcall_updated",
                view=self,
                action="update",
            )

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

            prev_id = filter_context.get("prev_message_id")
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

    def _on_query_created(self, pk: int, action: str, filter_context: dict) -> None:
        from server.models.queries.query import Query as QueryModel
        with self._callback_lock:
            try:
                query = QueryModel.objects.get(pk=pk)
            except QueryModel.DoesNotExist:
                return
            trigger_msg_pk = filter_context.get("trigger_message_id")
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
        