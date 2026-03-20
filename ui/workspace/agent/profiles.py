from ui.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.pyHtmlGui.pyhtmlgui.view.queryset_view import QuerySetView


class AgentProfileView(PyHtmlView):
    TEMPLATE_STR = """
    <b>Profile</b> <br>
    name = {{ pyview.subject.name }} <br>
    parent profile = {{ pyview.subject.parent }} <br>
    agent_version = {{ pyview.subject.agent_version }} <br>
    settings_overrides = {{ pyview.subject.settings_overrides }} <br>
    """

class AgentProfilesView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="agent-profiles-container" style="max-height: 300px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; margin-top: 20px;">
        <h4>profiles</h4>
        {{ pyview.agent_profile_view.render() }}
    </div>
    """
    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.agent_profile_view = QuerySetView(subject=subject, parent=self, item_class=AgentProfileView)
