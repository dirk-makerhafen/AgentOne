
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.lib.model_view import ModelView
from ui.workspace.workspace import WorkspaceView
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from ui.sidebar.sidebar import SidebarView
from ui.app import UiApp
from django.http.response import HttpResponse

@login_required
def ui(request):
    return render(request, 'pyhtmlgui_page.html', {})

class UiAppView(PyHtmlView):
    TEMPLATE_STR = """
    {{pyview.parent.css_view.render()}}
    <div class="resizable-container" data-orientation="horizontal">
        <div class="resizable-panel resizable-container " data-orientation="vertical" data-size-pc=15>
            {{ pyview.sidebar_view.render()}}
        </div>

        <div class="resizable-panel resizable-container" data-orientation="horizontal" data-size-pc=85 id="mainSplitViewContainer">
            {{ pyview.workspace_view.render()}}
        </div>
    </div>
        <script>
            parent = document.getElementById("{{pyview.uid}}");
            initializeSplitForContainer(parent);
            parent.querySelectorAll('.resizable-container').forEach(container => {
                initializeSplitForContainer(container);
            });
        </script>
    """

    def __init__(self, subject:UiApp, parent, **kwargs):
        self._subject = subject
        super().__init__(subject, parent, **kwargs)
        self.sidebar_view = SidebarView(subject, self) # Subject will be the main UiApp
        self.workspace_view = WorkspaceView(subject, self) # Subject will be the main UiApp

    def open_buildin_tab(self, tab_name):
        self.workspace_view.open_buildin_tab(tab_name)

    def open_instance_tab(self, instance):
        self.workspace_view.open_instance_tab(instance)

    def open_agent_tab(self, agent):
        self.workspace_view.open_agent_tab(agent)
