from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.session import Session
from server.models.enums.message_enums import MessageRole
from server.models.sessions.session import SessionModel
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.main.chat.composer.dropdown.model import ModelDropdown
from ui.main.chat.composer.dropdown.profile import ProfileDropdown
from ui.main.chat.composer.dropdown.reasoning import ReasoningDropdown
from ui.main.chat.composer.dropdown.toolsets import ToolsetsDropdown
from ui.main.chat.composer.dropdown.workspace import WorkspaceDropdown
from ui.main.chat.panel.mobileconfig import MobileConfigPanel
from ui.main.chat.composer.wrap.ctxindicator import CtxIndicatorWrap
from ui.main.chat.composer.wrap.model import ModelWrap
from ui.main.chat.composer.wrap.profile import ProfileWrap
from ui.main.chat.composer.wrap.reasoning import ReasoningWrap
from ui.main.chat.composer.wrap.toolsets import ToolsetsWrap
from ui.main.chat.composer.wrap.workspace import WorkspaceWrap
if TYPE_CHECKING:
    from ui.main.chat.composer.box import ComposerBox
from server.models.enums.message_enums import MessagePartType, MessageContentType


class ComposerFooter(PyHtmlView):
    DOM_ELEMENT_CLASS = 'composer-footer'
    TEMPLATE_STR = '''
        <div class="composer-left">
            <input type="file" id="fileInput" multiple accept="image/*,text/*,application/pdf,application/json,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,.md,.py,.js,.ts,.yaml,.yml,.toml,.csv,.sh,.txt,.log,.env,.xls,.xlsx,.doc,.docx,.zip,.tar,.gz,.tgz,.bz2,.xz" style="display:none">
            
            <button class="icon-btn" id="btnAttach" title="Attach files">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
            </button>
            
            <button class="icon-btn mic-btn" id="btnMic" title="Dictate" data-i18n-title="voice_dictate" style="display:none">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="1" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
            </button>
            
            <button class="icon-btn voice-mode-btn" id="btnVoiceMode" title="Voice mode" data-i18n-title="voice_mode_toggle" style="display:none">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><!-- Lucide audio-lines: signals two-way voice conversation, matches ChatGPT/Gemini convention. --><path d="M2 10v4"/><path d="M6 6v12"/><path d="M10 3v18"/><path d="M14 8v8"/><path d="M18 5v14"/><path d="M22 10v4"/></svg>
            </button>
            
            <div class="composer-divider" aria-hidden="true"></div>

            <button style="display:none" class="yolo-pill" id="yoloPill" type="button" onclick="cmdYolo()" style="display:none1" title="YOLO mode — click to disable" data-i18n-title="yolo_pill_title_active">
                <span class="yolo-pill-icon" aria-hidden="true">⚡</span>
                <span class="yolo-pill-label" data-i18n="yolo_pill_label">YOLO</span>
            </button>


            <button class="icon-btn composer-mobile-config-btn" id="composerMobileConfigBtn" type="button" onclick="toggleMobileComposerConfig()" title="Workspace, model, reasoning, and context settings" aria-label="Workspace, model, reasoning, and context settings" aria-haspopup="true" aria-expanded="false" aria-controls="composerMobileConfigPanel">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>
                <span class="composer-mobile-ctx-badge" id="composerMobileCtxBadge" aria-hidden="true" style="display:none">0</span>
            </button>
            

            

            {{ pyview.toolsets_wrap.render() }}
            
        </div>

        <div class="composer-right">
            <span class="composer-status" id="composerStatus_{{pyview.parent.uid}}">{{ pyview.status_text }}</span>

            {{ pyview.ctx_indicator_wrap.render() }}

            <span class="bg-badge" id="bgBadge" style="display:none1" title="Background tasks running">0</span>

            {% if pyview.send_mode == "queue" %}
            <button class="send-btn visible queue" id="btnQueue_{{pyview.parent.uid}}" onclick="window.sendChatDraft('{{pyview.parent.uid}}', 'queue')" title="Queue message — sends automatically when the current turn finishes" aria-label="Queue message">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M16 5H3"></path><path d="M16 12H3"></path><path d="M9 19H3"></path><path d="m16 16-3 3 3 3"></path><path d="M21 5v12a2 2 0 0 1-2 2h-6"></path></svg>
            </button>
            {% elif pyview.send_mode == "interrupt" %}
            <button class="send-btn visible interrupt" id="btnInterrupt_{{pyview.parent.uid}}" onclick="window.sendChatDraft('{{pyview.parent.uid}}', 'interrupt')" title="Interrupt and send — stops the current turn, then sends" aria-label="Interrupt and send">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 4v16"></path><path d="M6.029 4.285A2 2 0 0 0 3 6v12a2 2 0 0 0 3.029 1.715l9.997-5.998a2 2 0 0 0 .003-3.432z"></path></svg>
            </button>
            {% elif pyview.send_mode == "steer" %}
            <button class="send-btn visible steer" id="btnSteer_{{pyview.parent.uid}}" onclick="window.sendChatDraft('{{pyview.parent.uid}}', 'steer')" title="Steer current response — picked up by the running turn" aria-label="Steer current response">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><path d="m16.24 7.76-1.804 5.411a2 2 0 0 1-1.265 1.265L7.76 16.24l1.804-5.411a2 2 0 0 1 1.265-1.265z"></path></svg>
            </button>
            {% else %}
            <button class="send-btn" id="btnSend_{{pyview.parent.uid}}" title="Send message" aria-label="Send message" onclick="window.sendChatDraft('{{pyview.parent.uid}}')">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>
            </button>
            {% endif %}

            {% if pyview.is_busy %}
            <button class="send-btn visible stop" id="btnStop_{{pyview.parent.uid}}" onclick="pyview.stop_generation()" title="Stop generation" aria-label="Stop generation">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="5" width="14" height="14" rx="2"></rect></svg>
            </button>
            {% endif %}
        </div>

        {{ pyview.mobileconfig_panel.render() }}


        {{ pyview.toolsets_dropdown.render() }}


        <script>
        /* Image attachments: drag/drop, paste, and the #btnAttach picker.
           Element lookups happen at event time so listeners survive re-renders.  */
        (function () {
            window.__imgAttach = window.__imgAttach || [];
            var ATTACH_MAX_EDGE = 2048;

            function renderAttachTray() {
                var tray = document.getElementById('attachTray');
                if (!tray) return;
                tray.innerHTML = '';
                window.__imgAttach.forEach(function (item, i) {
                    var div = document.createElement('div');
                    div.className = 'attach-item';
                    var img = document.createElement('img');
                    img.src = item.content;
                    img.alt = item.name || 'attached image';
                    var btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'attach-remove';
                    btn.title = 'Remove attachment';
                    btn.innerHTML = '&times;';
                    btn.onclick = function () { window.__imgAttach.splice(i, 1); renderAttachTray(); };
                    div.appendChild(img);
                    div.appendChild(btn);
                    tray.appendChild(div);
                });
                tray.style.display = window.__imgAttach.length ? '' : 'none';
                tray.classList.toggle('has-files', window.__imgAttach.length > 0);
            }

            function attachImageFile(file) {
                var reader = new FileReader();
                reader.onload = function (ev) {
                    var image = new Image();
                    image.onload = function () {
                        var scale = Math.min(1, ATTACH_MAX_EDGE / Math.max(image.width, image.height));
                        var canvas = document.createElement('canvas');
                        canvas.width = Math.max(1, Math.round(image.width * scale));
                        canvas.height = Math.max(1, Math.round(image.height * scale));
                        var ctx = canvas.getContext('2d');
                        ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
                        var keepAlpha = file.type === 'image/png' || file.type === 'image/webp' || file.type === 'image/gif';
                        var dataUri = canvas.toDataURL(keepAlpha ? 'image/png' : 'image/jpeg', 0.85);
                        window.__imgAttach.push({type: 'MESSAGE', content_type: 'IMAGE', content: dataUri, name: file.name});
                        renderAttachTray();
                    };
                    image.onerror = function () { console.error('Could not decode image:', file.name); };
                    image.src = ev.target.result;
                };
                reader.readAsDataURL(file);
            }

            function handleAttachFiles(files) {
                for (var i = 0; i < files.length; i++) {
                    var f = files[i];
                    if (f.type && f.type.indexOf('image/') === 0 && f.type !== 'image/svg+xml') {
                        attachImageFile(f);
                    }
                }
            }

            window.sendChatDraft = function (uid, action) {
                var textEl = document.getElementById('input_' + uid);
                var text = textEl ? textEl.value : '';
                var parts = window.__imgAttach.slice();
                if (text && text.trim()) {
                    parts.push({type: 'MESSAGE', content_type: 'TEXT', content: text});
                }
                if (!parts.length) return;
                window.__imgAttach = [];
                renderAttachTray();
                if (textEl) textEl.value = '';
                pyview.send_action(parts, action || 'send');
            };

            if (!window.__imgAttachBound) {
                window.__imgAttachBound = true;
                document.addEventListener('click', function (e) {
                    if ((e.target.closest && e.target.closest('#btnAttach'))) {
                        var fi = document.getElementById('fileInput');
                        if (fi) fi.click();
                    }
                });
                document.addEventListener('change', function (e) {
                    if (e.target && e.target.id === 'fileInput' && e.target.files) {
                        handleAttachFiles(e.target.files);
                        e.target.value = '';
                    }
                });
                document.addEventListener('dragover', function (e) {
                    var box = e.target.closest ? e.target.closest('.composer-box') : null;
                    if (!box) return;
                    e.preventDefault();
                    e.stopPropagation();
                    e.dataTransfer.dropEffect = 'copy';
                    box.classList.add('drag-over');
                });
                document.addEventListener('dragleave', function (e) {
                    if (e.target.closest && e.target.closest('.composer-box')) return;
                    var cboxes = document.querySelectorAll('.composer-box.drag-over');
                    for (var i = 0; i < cboxes.length; i++) cboxes[i].classList.remove('drag-over');
                });
                document.addEventListener('drop', function (e) {
                    var box = e.target.closest ? e.target.closest('.composer-box') : null;
                    if (!box) return;
                    e.preventDefault();
                    e.stopPropagation();
                    box.classList.remove('drag-over');
                    handleAttachFiles(e.dataTransfer.files);
                });
                document.addEventListener('paste', function (e) {
                    var items = (e.clipboardData && e.clipboardData.items) || [];
                    var handled = false;
                    for (var i = 0; i < items.length; i++) {
                        var it = items[i];
                        if (it.kind === 'file' && it.type && it.type.indexOf('image/') === 0) {
                            var file = it.getAsFile();
                            if (file) { handleAttachFiles([file]); handled = true; }
                        }
                    }
                    if (handled) e.preventDefault();
                });
            }
        })();
        </script>

    '''
    # {{ pyview.profile_wrap.render() }}
    # {{ pyview.workspace_wrap.render() }}     
    # {{ pyview.model_wrap.render() }}
    # {{ pyview.reasoning_wrap.render() }}

    # {{ pyview.workspace_dropdown.render() }}
    # {{ pyview.profile_dropdown.render() }}
    # {{ pyview.model_dropdown.render() }}
    # {{ pyview.reasoning_dropdown.render() }}


    def __init__(self, subject:Session, parent: ComposerBox, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.parent:ComposerBox
        self._last_activity_key: tuple | None = None
        self._subscribe_activity_events()
        self.mobileconfig_panel = MobileConfigPanel(subject, self)

        self.profile_wrap = ProfileWrap(subject, self)
        self.workspace_wrap = WorkspaceWrap(subject, self)
        self.model_wrap = ModelWrap(subject, self)
        self.reasoning_wrap = ReasoningWrap(subject, self)
        self.toolsets_wrap = ToolsetsWrap(subject, self)
        
        self.profile_dropdown = ProfileDropdown(subject, self)
        self.workspace_dropdown = WorkspaceDropdown(subject, self)
        self.model_dropdown = ModelDropdown(subject, self)
        self.reasoning_dropdown = ReasoningDropdown(subject, self)
        self.toolsets_dropdown = ToolsetsDropdown(subject, self)

        self.ctx_indicator_wrap = CtxIndicatorWrap(subject, self)

    # ------------------------------------------------------------------
    # Send-button state (stop / queue / interrupt / steer)
    # ------------------------------------------------------------------

    @property
    def is_busy(self) -> bool:
        """True while a turn is running or pending for this session."""
        try:
            return bool(self.subject.is_busy())
        except Exception:  # pylint: disable=broad-exception-caught
            return False

    @property
    def send_mode(self) -> str:
        """Which primary button to show: ``send`` when idle, otherwise the
        action matching the session scheduler strategy (``queue``,
        ``interrupt`` or ``steer`` for merge; parallel keeps ``send``)."""
        if not self.is_busy:
            return "send"
        try:
            strategy = self.subject.scheduler_strategy
        except Exception:  # pylint: disable=broad-exception-caught
            strategy = None
        if strategy == "interrupt":
            return "interrupt"
        if strategy == "merge":
            return "steer"
        if strategy == "parallel":
            return "send"
        return "queue"

    @property
    def status_text(self) -> str:
        """Short composer status line (working / queued count)."""
        if not self.is_busy:
            return ""
        try:
            from server.models.enums.task_enums import TaskCallStatusDetail
            from server.models.tasks.agent_task_call import AgentTaskCall
            queued = AgentTaskCall.objects.filter(
                session=self.subject.model,
                status_detail=TaskCallStatusDetail.WAITING_QUEUE,
            ).count()
        except Exception:  # pylint: disable=broad-exception-caught
            queued = 0
        if queued:
            return f"Working… · {queued} queued"
        return "Working…"

    def _subscribe_activity_events(self) -> None:
        """Refresh the buttons when turn activity changes.

        ``Messages`` watches the same models for the chat log; the footer
        watches them too so the send/stop buttons flip as turns start and
        end.  Redis subscriptions are per UI instance, so unlike the old
        ModelObserver watches there is no stale-subscription clearing and
        no ordering constraint vs ``Messages.__init__``.
        """
        try:
            from ui.lib.model_view import orm_subscribe
        except Exception:  # pylint: disable=broad-exception-caught
            return
        try:
            session_id = self.subject.model.pk
            for key in (
                f"Message.session:{session_id}",
                f"Query.session:{session_id}",
                f"AgentTaskCall.session:{session_id}",
            ):
                orm_subscribe(self, key, self._on_orm_event)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def _on_orm_event(self, key=None, model=None, pk=None, action=None, data=None) -> None:
        """Redis observable callback: turn activity changed, maybe re-render."""
        self._on_activity_event()

    def _on_activity_event(self, pk: int | None = None, action: str | None = None, filter_context: dict | None = None) -> None:
        """Re-render the buttons, but only when the busy/mode state flipped
        (task-call events fire on every FSM transition — re-rendering each
        time would collapse open composer dropdowns for no reason)."""
        try:
            key = (self.is_busy, self.send_mode)
        except Exception:  # pylint: disable=broad-exception-caught
            return
        if key != self._last_activity_key:
            self._last_activity_key = key
            try:
                self.update()
            except Exception:  # pylint: disable=broad-exception-caught
                pass

    def send(self, parts):
        '''
        parts:  list from parse_llm_response of Parts
            Parts is dict with minimal keys:
                type: message, reasoning, toolcall
                content_type: text|image|template|json
                content: str|dict
        '''
        self.send_action(parts, "send")

    def send_action(self, parts, action: str = "send"):
        """Dispatch the composer draft according to *action*:

        - ``send`` — strategy-aware default (queue parks, interrupt stops +
          sends, merge steers while busy).
        - ``queue`` — park until the live turn finishes.
        - ``interrupt`` — stop the live turn, then send immediately.
        - ``steer`` — insert into the running turn (merge).
        - ``stop`` — cancel the live turn (draft is discarded).
        """
        if isinstance(parts, str):
            parts = [{
                "type":  MessagePartType.MESSAGE,
                "content_type": MessageContentType.TEXT,
                "content": parts
            },]
        self.eval_javascript(f"document.getElementById('input_{self.parent.uid}').value = ''", skip_results=True)
        try:
            if action == "stop":
                self.subject.stop_generation()
            elif action == "queue":
                self.subject.queue_message(parts)
            elif action == "interrupt":
                self.subject.stop_generation()
                self.subject.add_user_message(parts, force=True)
            elif action == "steer":
                self.subject.steer_message(parts)
            else:
                self.subject.add_user_message(parts)
        except Exception as e:  # pylint: disable=broad-exception-caught
            from server.models.message import Message as Msg
            from runtime.events import publish_model_event
            session_version = self.subject.get_version_model()
            prev_message = self.subject.get_last_message()
            msg = Msg.objects.create(role=MessageRole.USER, session=session_version.session, session_version=session_version, prev_message=prev_message)
            msg.add_part(type=MessagePartType.MESSAGE, content_type=MessageContentType.TEXT, content=str(e))
            publish_model_event(msg, "create")
        self._last_activity_key = None
        try:
            self.update()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def stop_generation(self):
        """Cancel the running turn ("Stop generation" button)."""
        try:
            self.subject.stop_generation()
        except Exception as e:  # pylint: disable=broad-exception-caught
            from server.models.message import Message as Msg
            from runtime.events import publish_model_event
            session_version = self.subject.get_version_model()
            prev_message = self.subject.get_last_message()
            msg = Msg.objects.create(role=MessageRole.USER, session=session_version.session, session_version=session_version, prev_message=prev_message)
            msg.add_part(type=MessagePartType.MESSAGE, content_type=MessageContentType.TEXT, content=str(e))
            publish_model_event(msg, "create")
        self._last_activity_key = None
        try:
            self.update()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def close_dropdowns(self):
        self.profile_dropdown.close()
        self.workspace_dropdown.close()
        self.model_dropdown.close()
        self.reasoning_dropdown.close()
        self.toolsets_dropdown.close()

    def toggleProfileDropdown(self):
        self.profile_dropdown.toggle()
    def toggleReasoningDropdown(self):
        self.reasoning_dropdown.toggle()
    def toggleToolsetsDropdown(self):
        self.toolsets_dropdown.toggle()
    def toggleComposerWsDropdown(self):
        self.workspace_dropdown.toggle()
    def toggleModelDropdown(self):
        self.model_dropdown.toggle()

        
        
        