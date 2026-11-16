from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from runtime.session.session import Session
from server.models.sessions.session import SessionModel

if TYPE_CHECKING:
    from ui.main.rightpanel.session.rightpanel_session import RightPanelSession
    from ui.app import UiApp


class RightPanelSessionHistory(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
    TEMPLATE_STR = '''
        <div class="panel-header">
            <span>History</span>
            <div class="panel-actions">
                <button class="panel-icon-btn" onclick="pyview.refresh()" title="Refresh">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
                </button>
            </div>
        </div>
        <div style="flex:1;overflow-y:auto;padding:8px;display:flex;flex-direction:column;gap:8px">
            <!-- Search controls -->
            <div style="display:flex;flex-direction:column;gap:6px">
                <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">
                    <input type="text" id="history-search-input" placeholder="Search messages..." style="flex:1;min-width:150px;padding:4px 8px;font-size:12px;border:1px solid var(--border);border-radius:4px;background:var(--input-bg);color:var(--text)" oninput="pyview.onSearchInput(this.value)">
                    <button class="panel-icon-btn" onclick="pyview.clearSearch()" title="Clear search">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                    </button>
                </div>
                <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;font-size:12px;color:var(--muted)">
                    <label style="display:flex;align-items:center;gap:4px;cursor:pointer">
                        <input type="checkbox" id="history-pending-only" {% if pyview.pending_only %}checked{% endif %} onchange="pyview.setPendingOnly(this.checked)">
                        <span>Pending only (ingest_user_message)</span>
                    </label>
                    <label style="display:flex;align-items:center;gap:4px;cursor:pointer">
                        <input type="checkbox" id="history-resolved-view" {% if pyview.resolved_view %}checked{% endif %} onchange="pyview.setResolvedView(this.checked)">
                        <span>Resolved view</span>
                    </label>
                    <label style="display:flex;align-items:center;gap:4px;cursor:pointer">
                        <input type="checkbox" id="history-include-hidden" {% if pyview.include_hidden %}checked{% endif %} onchange="pyview.setIncludeHidden(this.checked)">
                        <span>Include hidden/INFO</span>
                    </label>
                    <label style="display:flex;align-items:center;gap:4px;cursor:pointer">
                        <input type="checkbox" id="history-include-compacted" {% if pyview.include_compacted %}checked{% endif %} onchange="pyview.setIncludeCompacted(this.checked)">
                        <span>Include compacted</span>
                    </label>
                    <label style="display:flex;align-items:center;gap:4px;cursor:pointer">
                        <input type="checkbox" id="history-include-subsessions" {% if pyview.include_subsessions %}checked{% endif %} onchange="pyview.setIncludeSubsessions(this.checked)">
                        <span>Include sub-sessions</span>
                    </label>
                </div>
            </div>

            <!-- Results -->
            <div style="flex:1;overflow-y:auto;min-height:0">
                {% if pyview.results %}
                    {% for result in pyview.results %}
                    <div class="history-entry" style="padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--card-bg);font-size:12px">
                        <div style="display:flex;gap:8px;align-items:flex-start;margin-bottom:4px">
                            <span class="detail-badge {{ result.role_badge }}" style="font-size:10px;padding:1px 6px;flex-shrink:0">{{ result.role }}</span>
                            <span style="color:var(--muted);font-size:10px;flex-shrink:0">{{ result.created_at }}</span>
                            {% if result.beyond_compaction %}
                            <span class="detail-badge warn" style="font-size:9px;padding:1px 4px">compacted</span>
                            {% endif %}
                            {% if result.hidden_from_llm %}
                            <span class="detail-badge info" style="font-size:9px;padding:1px 4px">hidden</span>
                            {% endif %}
                            {% if result.tool_call_name and result.tool_call_name != "ingest_user_message" %}
                            <span class="detail-badge" style="font-size:9px;padding:1px 4px;background:var(--accent-bg);color:var(--accent)">{{ result.tool_call_name }}</span>
                            {% endif %}
                            {% if result.session_pk %}
                            <span class="detail-badge" style="font-size:9px;padding:1px 4px;background:var(--muted-bg);color:var(--muted)">{{ result.agent }}:{{ result.session_pk }}</span>
                            {% endif %}
                        </div>
                        <div style="color:var(--text);white-space:pre-wrap;word-break:break-word;font-family:inherit;line-height:1.4">{{ result.preview }}</div>
                        {% if result.preview_truncated %}
                        <button class="panel-icon-btn" onclick="pyview.inspectResult({{ result.message_pk }})" title="View full message" style="margin-top:4px;font-size:11px;padding:2px 8px">View full</button>
                        {% endif %}
                    </div>
                    {% endfor %}
                    {% if pyview.has_more %}
                    <button class="panel-head-btn" onclick="pyview.loadMore()" style="width:100%;margin-top:8px">Load more ({{ pyview.total_count }} total)</button>
                    {% endif %}
                {% else %}
                    <div style="font-size:12px;color:var(--muted);padding:24px;text-align:center">No messages found.</div>
                {% endif %}
            </div>
        </div>
    '''

    def __init__(self, subject: SessionModel, parent: RightPanelSession, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.session = Session(session_model=subject)
        self._search_text = ""
        self._pending_only = True
        self._resolved_view = True
        self._include_hidden = False
        self._include_compacted = True
        self._include_subsessions = False
        self._limit = 50
        self._offset = 0
        self._results: list[dict] = []
        self._total_count = 0
        self._has_more = False
        self._search_debounce_timer = None
        self.refresh()

    @property
    def pending_only(self) -> bool:
        return self._pending_only

    @property
    def resolved_view(self) -> bool:
        return self._resolved_view

    @property
    def include_hidden(self) -> bool:
        return self._include_hidden

    @property
    def include_compacted(self) -> bool:
        return self._include_compacted

    @property
    def include_subsessions(self) -> bool:
        return self._include_subsessions

    @property
    def results(self) -> list[dict]:
        return self._results

    @property
    def total_count(self) -> int:
        return self._total_count

    @property
    def has_more(self) -> bool:
        return self._has_more

    def onSearchInput(self, value: str) -> None:
        self._search_text = value
        self._debounced_search()

    def _debounced_search(self) -> None:
        if self._search_debounce_timer:
            try:
                self._instance.call_javascript("clearTimeout", [self._search_debounce_timer], skip_results=True)
            except Exception:
                pass
        try:
            self._search_debounce_timer = self._instance.call_javascript(
                "setTimeout", ["pyview._doSearch()", 300], skip_results=True
            )
        except Exception:
            self._do_search()

    def _do_search(self) -> None:
        self._offset = 0
        self._search()

    def _doSearch(self) -> None:
        """JS callback for debounced search."""
        self._do_search()

    def clearSearch(self) -> None:
        self._search_text = ""
        self._offset = 0
        try:
            self._instance.call_javascript(
                "pyhtmlgui.eval_script",
                ["document.getElementById('history-search-input').value = ''", {}],
                skip_results=True,
            )
        except Exception:
            pass
        self._search()

    def setPendingOnly(self, value: bool) -> None:
        self._pending_only = value
        self._offset = 0
        self._search()

    def setResolvedView(self, value: bool) -> None:
        self._resolved_view = value
        self._offset = 0
        self._search()

    def setIncludeHidden(self, value: bool) -> None:
        self._include_hidden = value
        self._offset = 0
        self._search()

    def setIncludeCompacted(self, value: bool) -> None:
        self._include_compacted = value
        self._offset = 0
        self._search()

    def setIncludeSubsessions(self, value: bool) -> None:
        self._include_subsessions = value
        self._offset = 0
        self._search()

    def loadMore(self) -> None:
        self._offset += self._limit
        self._search(append=True)

    def inspectResult(self, message_pk: int) -> None:
        """Open the full message in the inspect history tool."""
        # This could open a modal or navigate to the message in chat
        # For now, just log it
        pass

    def refresh(self) -> None:
        self._offset = 0
        self._search()

    def _search(self, append: bool = False) -> None:
        # Build tool arguments
        # resolved_view=True means show only non-compacted (resolved) messages
        # include_compacted is the inverse: True = include compacted messages
        include_compacted = not self._resolved_view if self._resolved_view is not None else self._include_compacted

        kwargs = {
            "text": self._search_text or None,
            "include_hidden": self._include_hidden,
            "include_compacted": include_compacted,
            "include_subsessions": self._include_subsessions,
            "limit": self._limit,
            "offset": self._offset,
            "order": "newest",
        }

        if self._pending_only:
            kwargs["tool_call_name"] = "ingest_user_message"
            # When searching for pending user messages, we want MESSAGE parts from user role
            kwargs["part_type"] = "MESSAGE"
            kwargs["role"] = "user"

        # Call the tool synchronously via the session's tool mechanism
        try:
            tool = self.session.get_tool("search_own_history")
            if tool is None:
                result = {"error": "search_own_history tool not available in this session"}
            else:
                result = tool.call(**kwargs)
        except Exception as exc:
            result = {"error": f"search_own_history failed: {exc}"}

        if result.get("error"):
            # Handle error
            if not append:
                self._results = []
            return

        new_results = result.get("results", [])
        self._total_count = result.get("total_count", 0)
        self._has_more = result.get("has_more", False)

        # Filter out call_llm_direct calls in UI layer
        filtered = [
            r for r in new_results
            if r.get("tool_call_name") != "call_llm_direct"
        ]

        if append:
            self._results.extend(filtered)
        else:
            self._results = filtered

        self.update()