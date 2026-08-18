from __future__ import annotations
import json
import threading
from typing import TYPE_CHECKING
from runtime.session.session import Session
from server.models.message import Message, MessagePart
from server.models.enums.message_enums import MessagePartType
from ui.lib.model_view import ModelView
from ui.app import UiApp

if TYPE_CHECKING:
    from ui.main.chat.chat import Chat
    from ui.main.chat.messages.messages import Messages


class ChatTocView(ModelView):
    """Right-side table-of-contents rail for long chats.

    One small pill button per compaction boundary in the session's chain
    (oldest -> newest).  Clicking a pill jumps the chat scroll container so
    that compaction message is at the top of the viewport.  A scroll listener
    keeps the pill for the segment currently in view highlighted.
    """

    DOM_ELEMENT_CLASS = "chat-toc"
    TEMPLATE_STR = '''
        <div class="chat-toc-rail" role="navigation" aria-label="Chat sections">
            {% for seg in pyview.segments %}
                <button type="button" class="chat-toc-item" data-toc-index="{{ loop.index0 }}" aria-label="{{ seg.label }}" title="{{ seg.label }}" onclick="pyview.jump({{ loop.index0 }})"></button>
            {% endfor %}
        </div>
        <script>
            (function(){
                var pks = {{ pyview.compaction_pks | safe }};
                var c = document.getElementById('{{ pyview.messages_uid }}');
                if (!pks.length || !c) return;
                var rail = document.getElementById('{{ pyview.uid }}');
                var items = Array.prototype.slice.call(rail.querySelectorAll('.chat-toc-item[data-toc-index]'));
                function rowFor(pk){
                    return c.querySelector('[data-pk="' + pk + '"]');
                }
                function updateActive(){
                    var mid = c.scrollTop + c.clientHeight * 0.4;
                    var active = -1;
                    for (var i = 0; i < pks.length; i++) {
                        var r = rowFor(pks[i]);
                        if (!r) continue;
                        var off = r.getBoundingClientRect().top - c.getBoundingClientRect().top + c.scrollTop;
                        if (off <= mid) active = i;
                    }
                    for (var j = 0; j < items.length; j++) {
                        items[j].classList.toggle('active', j === active);
                    }
                }
                c.addEventListener('scroll', updateActive, {passive:true});
                setTimeout(updateActive, 300);
            })();
        </script>
    '''

    def __init__(self, subject: Session, parent: Chat, messages_view: Messages, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.messages_view = messages_view
        self._session_id = subject.model.pk
        self._segments: list[dict] | None = None
        app = UiApp.get_instance()
        if app is not None:
            app.model_observer.watch(
                Message,
                filter={"session_id": self._session_id},
                callback_name="_on_message_created",
                view=self,
                action="create",
            )
        self._segments_lock = threading.Lock()

    @property
    def messages_uid(self) -> str:
        return self.messages_view.uid

    @property
    def compaction_pks(self) -> str:
        return json.dumps([seg["pk"] for seg in self.segments])

    @property
    def segments(self) -> list[dict]:
        with self._segments_lock:
            if self._segments is None:
                self._reload_segments()
            return self._segments

    def _reload_segments(self) -> None:
        """Collect compaction messages in chain order (oldest -> newest).

        Compaction summaries are always appended at the tail when they are
        created and never repointed to become ancestors of later compactions,
        so within one session ``pk`` (creation) order equals chain order.
        """
        pks = set(
            MessagePart.objects.filter(
                message__session_id=self._session_id,
                type=MessagePartType.COMPACTION,
            ).values_list("message_id", flat=True)
        )
        self._segments = [
            {
                "pk": msg.pk,
                "label": "Section %d" % (i + 1),
            }
            for i, msg in enumerate(
                Message.objects.filter(pk__in=pks).order_by("pk")
            )
        ]

    def jump(self, index: int) -> None:
        segments = self.segments
        if index < 0 or index >= len(segments):
            return
        self.messages_view.jump_to_message(segments[index]["pk"])

    def _on_message_created(self, pk: int, action: str, filter_context: dict) -> None:
        is_compaction = MessagePart.objects.filter(
            message_id=pk,
            type=MessagePartType.COMPACTION,
        ).exists()
        if is_compaction:
            with self._segments_lock:
                self._segments = None
            self.update()