from __future__ import annotations
from ui.lib.model_view import ModelView
from server.models.agents.agent_instance import AgentInstance
from server.models.agents.agent_instance_version import AgentInstanceVersion
from server.models.agents.agent_version import AgentVersion
from server.models.agents.agent_profile import AgentProfile


class InstanceHeaderView(ModelView):
    DOM_ELEMENT_CLASS = "InstanceHeaderView"

    TEMPLATE_STR = """
        <div class="instance-header-inner">
            <div class="header-group">
                <span class="header-agent-name">
                    <i class="fa fa-users header-icon"></i>
                    {{ pyview.subject.agent.name }}
                </span>
                <span class="header-instance-name"
                      contenteditable="true"
                      onblur="pyview.save_name(this.innerText)"
                      title="Click to rename">
                    {{ pyview.subject.name or 'Unnamed' }}
                </span>
            </div>

            <div class="header-group">
                {% if pyview.agent_version %}
                    <span class="header-badge">
                        <i class="fa fa-code"></i> v{{ pyview.agent_version.version_number }}
                    </span>
                {% endif %}
                <span class="header-badge">
                    <i class="fa fa-code-fork"></i>
                    {{ pyview.pinned_profile.name if pyview.pinned_profile else 'default' }}
                </span>
            </div>

            <div class="header-group header-group-tokens">
                <span class="header-badge" title="Prompt / completion tokens">
                    <i class="fa fa-arrow-up"></i> {{ pyview.prompt_tokens }}
                    &nbsp;
                    <i class="fa fa-arrow-down"></i> {{ pyview.completion_tokens }}
                </span>
            </div>
        </div>
    """

    CSS_STR = """
.InstanceHeaderView {
    background: var(--bg);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
}
.instance-header-inner {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 4px 12px;
    flex-wrap: wrap;
    min-height: 32px;
}
.header-group {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
}
.header-group-tokens { margin-left: auto; }

.header-icon { color: var(--text-muted); margin-right: 4px; font-size: 0.9em; }

.header-agent-name {
    font-weight: 600;
    font-size: 0.95em;
    white-space: nowrap;
}
.header-instance-name {
    font-size: 0.88em;
    color: var(--text-muted);
    border-bottom: 1px dashed var(--border);
    cursor: text;
    padding: 0 2px;
    transition: border-color 0.15s;
    white-space: nowrap;
}
.header-instance-name:focus {
    outline: none;
    border-bottom-color: var(--accent);
    color: var(--text);
}
.header-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 0.8em;
    color: var(--text-muted);
    background: var(--bg-subtle);
    border: 1px solid var(--border-light);
    border-radius: 10px;
    padding: 1px 8px;
    white-space: nowrap;
}
    """

    def __init__(self, subject: AgentInstance, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.agent_version: AgentVersion | None = None
        self.pinned_profile: AgentProfile | None = None
        self._reload()

    def _reload(self):
        latest: AgentInstanceVersion | None = self.subject.latest_agent_instance_version
        if latest:
            self.agent_version = latest.agent_version
            self.pinned_profile = latest.pinned_agent_profile

    @property
    def prompt_tokens(self) -> int:
        from django.db.models import Sum
        return self.subject.queries.aggregate(
            total=Sum('related_response__prompt_tokens')
        )['total'] or 0

    @property
    def completion_tokens(self) -> int:
        from django.db.models import Sum
        return self.subject.queries.aggregate(
            total=Sum('related_response__completion_tokens')
        )['total'] or 0

    def save_name(self, new_name: str):
        new_name = new_name.strip()
        if new_name and self.subject.name != new_name:
            # TODO: AgentInstance is immutable — needs new instance creation
            print(f"[InstanceHeaderView] name change to {new_name!r} — not yet persisted")
        self.update()