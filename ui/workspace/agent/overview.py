from __future__ import annotations
from server.models.agents.agent_version import AgentVersion
from server.models.agents.agent_instance import AgentInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.lib.queryset_view import QuerySetView
from ui.workspace.agent.tasks import AgentTaskDefinitionsView, AgentTaskDefinitionView
from ui.workspace.agent.settings import AgentSettingsView
from ui.lib.model_view import ModelView


# ---------------------------------------------------------------------------
# Version views
# ---------------------------------------------------------------------------

class AgentVersionView(ModelView):
    """Detail table for a single AgentVersion."""
    DOM_ELEMENT = "table"
    DOM_ELEMENT_CLASS = "AgentVersionView agent-version-table"

    TEMPLATE_STR = """
        <thead>
            <tr><th>Field</th><th>Value</th></tr>
        </thead>
        <tbody>
            <tr>
                <td>Version</td>
                <td>{{ pyview.subject.version_number }}</td>
            </tr>
            <tr>
                <td>Parent</td>
                <td>
                    {% if pyview.subject.parent %}
                        v{{ pyview.subject.parent.version_number }}
                    {% else %}
                        —
                    {% endif %}
                </td>
            </tr>
            <tr>
                <td>Source path</td>
                <td>{{ pyview.subject.source_path }}</td>
            </tr>
            <tr>
                <td>Class name</td>
                <td>{{ pyview.subject.class_name }}</td>
            </tr>
            <tr>
                <td>Sub-agents</td>
                <td>{{ pyview.subject.sub_agent_versions.count() }}</td>
            </tr>
            <tr>
                <td colspan="2"><strong>Profile</strong></td>
            </tr>
            {{ pyview.profile_view.render() }}
            <tr>
                <td colspan="2"><strong>Task definitions</strong></td>
            </tr>
            {{ pyview.task_definitions_view.render() }}
            <tr>
                <td colspan="2"><strong>Available tools</strong></td>
            </tr>
            {% for tool in pyview.subject.available_tools.all() %}
                <tr>
                    <td>{{ tool.task_definition.name }}</td>
                    <td>{{ tool.tool_agent_version.agent.name }}</td>
                </tr>
            {% endfor %}
        </tbody>
    """

    def __init__(self, subject: AgentVersion, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.profile_view = AgentSettingsView(subject.profile, self)
        self.task_definitions_view = AgentTaskDefinitionsView(
            subject=subject.task_definitions.all(),
            parent=self,
            item_class=AgentTaskDefinitionView,
        )


class AgentVersionsView(ModelView):
    """Shows the latest agent version — expandable to full history later."""
    DOM_ELEMENT_CLASS = "AgentVersionsView"

    TEMPLATE_STR = """
        <h4>Latest version</h4>
        {% if pyview.latest_view %}
            {{ pyview.latest_view.render() }}
        {% else %}
            <p class="text-muted small">No versions registered yet.</p>
        {% endif %}
    """

    def __init__(self, subject, parent, **kwargs):
        """Subject is the agent_versions queryset (ordered by -version_number)."""
        super().__init__(subject, parent, **kwargs)
        latest = subject.first()
        self.latest_view = AgentVersionView(latest, self) if latest else None


# ---------------------------------------------------------------------------
# Instance views
# ---------------------------------------------------------------------------

class AgentInstanceView(ModelView):
    """One-row summary of an AgentInstance."""
    DOM_ELEMENT_CLASS = "AgentInstanceView agent-instance-row"

    TEMPLATE_STR = """
        <div class="instance-row-inner">
            <span class="instance-name">{{ pyview.subject.name or 'unnamed' }}</span>
            {% if pyview.subject.latest_agent_instance_version %}
                <span class="text-muted small">
                    v{{ pyview.subject.latest_agent_instance_version.agent_version.version_number }}
                    · #{{ pyview.subject.latest_agent_instance_version.pk }}
                    {% if pyview.subject.latest_agent_instance_version.workingdir %}
                        · {{ pyview.subject.latest_agent_instance_version.workingdir }}
                    {% endif %}
                </span>
            {% endif %}
            <button class="btn btn-xs btn-default"
                    onclick="pyview.open_tab()">
                Open
            </button>
        </div>
    """

    def __init__(self, subject: AgentInstance, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)

    def open_tab(self):
        # Walk up to the workspace view which has open_instance_tab
        node = self.parent
        while node is not None:
            if hasattr(node, 'open_instance_tab'):
                node.open_instance_tab(self.subject.pk)
                return
            node = getattr(node, 'parent', None)


class AgentInstancesView(ModelView):
    """List of all instances for this agent."""
    DOM_ELEMENT_CLASS = "AgentInstancesView"

    TEMPLATE_STR = """
        <h4>Instances</h4>
        {{ pyview.instances_view.render() }}
    """

    def __init__(self, subject, parent, **kwargs):
        """Subject is the agent_instances queryset."""
        super().__init__(subject, parent, **kwargs)
        self.instances_view = QuerySetView(
            subject=subject,
            parent=self,
            item_class=AgentInstanceView,
        )



# ---------------------------------------------------------------------------
# Sub-Agent views
# ---------------------------------------------------------------------------

class SubAgentVersionView(ModelView):
    """One-row summary of an Agent."""
    DOM_ELEMENT_CLASS = "SubAgentVersionView agent-version-row"

    TEMPLATE_STR = """
        <div class="instance-row-inner">
            <span class="instance-name">{{ pyview.subject.agent.name or 'unnamed' }}</span>
            {% if pyview.subject %}
                <span class="text-muted small">
                    v{{ pyview.subject.version_number }}
                    · #{{ pyview.subject.pk }}
                    {% if pyview.subject.workingdir %}
                        · {{ pyview.subject.workingdir }}
                    {% endif %}
                </span>
            {% endif %}
            <button class="btn btn-xs btn-default"
                    onclick="pyview.open_agent_tab()">
                Open
            </button>
        </div>
    """

    def __init__(self, subject: AgentVersion, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)

    def open_agent_tab(self):
        # Walk up to the workspace view which has open_agent_tab
        node = self.parent
        while node is not None:
            if hasattr(node, 'open_agent_tab'):
                node.open_agent_tab(self.subject.agent)
                return
            node = getattr(node, 'parent', None)

class SubAgentVersionsView(ModelView):
    """List of all sub agents for this agent."""
    DOM_ELEMENT_CLASS = "SubAgentVersionsView"
    TEMPLATE_STR = """
        <h4>Sub Agents</h4>
        {{ pyview.instances_view.render() }}
    """

    def __init__(self, subject, parent, **kwargs):
        """Subject is the agent queryset."""
        super().__init__(subject, parent, **kwargs)
        self.instances_view = QuerySetView(subject=subject, parent=self, item_class=SubAgentVersionView)


    