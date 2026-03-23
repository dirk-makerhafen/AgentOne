from __future__ import annotations
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.lib.queryset_view import QuerySetView
from ui.lib.model_view import ModelView


class AgentProfileView(ModelView):
    """Detail view for a single AgentProfile."""
    DOM_ELEMENT_CLASS = "AgentProfileView agent-profile-item"

    TEMPLATE_STR = """
        <div class="profile-inner">
            <div class="profile-name">
                <strong>{{ pyview.subject.name or 'unnamed' }}</strong>
                {% if pyview.subject.parent %}
                    <span class="text-muted small">
                        child of {{ pyview.subject.parent.name or pyview.subject.parent.pk }}
                    </span>
                {% endif %}
            </div>
            <div class="profile-fields small">
                model={{ pyview.subject.aimodel.name if pyview.subject.aimodel else '—' }}
                mode={{ pyview.subject.execution_mode }}
                retries={{ pyview.subject.max_retries }}
                priority={{ pyview.subject.priority }}
                steps={{ pyview.subject.max_task_steps }}
                history={{ pyview.subject.max_history_messages }}
            </div>
            {% if pyview.subject.variant_defs %}
                <div class="profile-variants small text-muted">
                    {{ pyview.subject.variant_defs | length }} variant(s) defined
                </div>
            {% endif %}
        </div>
    """


class AgentProfilesView(ModelView):
    """List of AgentProfiles associated with an agent version."""
    DOM_ELEMENT_CLASS = "AgentProfilesView"

    TEMPLATE_STR = """
        <div class="profiles-container">
            <h4>Profiles</h4>
            {{ pyview.profiles_view.render() }}
        </div>
    """

    def __init__(self, subject, parent, **kwargs):
        """Subject is a queryset of AgentProfile objects."""
        super().__init__(subject, parent, **kwargs)
        self.profiles_view = QuerySetView(
            subject=subject,
            parent=self,
            item_class=AgentProfileView,
        )