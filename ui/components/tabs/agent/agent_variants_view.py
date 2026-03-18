from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
from ui.pyHtmlGui.pyhtmlgui.view.querySetView import QuerySetView


class AgentVariantView(PyHtmlView):
    TEMPLATE_STR = """
    <b>Variant</b> <br>
    name = {{ pyview.subject.name }} <br>
    parent variant = {{ pyview.subject.parent }} <br>
    agent_version = {{ pyview.subject.agent_version }} <br>
    settings_overrides = {{ pyview.subject.settings_overrides }} <br>
    """

class AgentVariantsView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="agent-variants-container" style="max-height: 300px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; margin-top: 20px;">
        <h4>variants</h4>
        {{ pyview.agent_variant_view.render() }}
    </div>
    """
    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.agent_variant_view = QuerySetView(subject=subject, parent=self, item_class=AgentVariantView)
