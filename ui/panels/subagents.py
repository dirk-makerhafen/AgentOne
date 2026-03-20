
from ui.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from server.models.agents.agent_version import AgentVersion
from ui.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.pyHtmlGui.pyhtmlgui.view.queryset_view import QuerySetView


class SidebarSubagentView(PyHtmlView):
    DOM_ELEMENT = "li"
    DOM_ELEMENT_CLASS = "SidebarSubagentView list-group-item"
    TEMPLATE_STR = '''
        <i class="fa fa-sitemap list-icon"></i>
        <strong>{{ pyview.agent_version }}</strong> (ID: {{ pyview.agent_version.pk }})
        <span class="pull-right badge {% if pyview.agent_version.status == 'IDLE' %}badge-success{% else %}badge-warning{% endif %}"></span>
        <p class="text-muted small">Created: {{ pyview.agent_version.created_at }}</p>

    '''
    def __init__(self, subject, parent: PyHtmlView | PyHtmlGuiInstance, **kwargs):
        self.agent_version = subject
        super().__init__(subject, parent, **kwargs)


class SidebarSubagentsView(PyHtmlView):
    TEMPLATE_STR = """
    <div role="tabpanel">
        <div class="sidebar-list-header">
            <h4>Sub-Agents</h4>
        </div>
        <div class="sidebar-list-body subagents-list-body">
            {{pyview.sub_agent_view.render()}}
        </div>
    </div>
    """

    def __init__(self, subject: AgentVersion, parent: PyHtmlView | PyHtmlGuiInstance, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.sub_agent_view = QuerySetView(subject=subject.sub_agent_versions, parent=self, item_class=SidebarSubagentView, dom_element="ul", dom_element_class="list-group")
