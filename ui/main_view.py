
from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from ui.components.sidebar.sidebar import SidebarContainerView
from ui.components.tabs.tabs import TabsView
from ui.main_app import UiApp

@login_required
def ui(request):
    return render(request, 'pyhtmlgui_page.html', {})

class UiAppView(PyHtmlView):
    TEMPLATE_STR = """
    <style>
        .fade {
            opacity: 100%;
        }
    </style>
    <div class="resizable-container" data-orientation="horizontal">
        <div class="resizable-panel resizable-container " data-orientation="vertical" data-size-pc=15>
            {{ pyview.sidebar_view.render()}}
        </div>

        <div class="resizable-panel resizable-container" data-orientation="horizontal" data-size-pc=85 id="mainSplitViewContainer">
            {{ pyview.tabs_view.render()}}
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
        super().__init__(subject, parent, **kwargs)
        self.sidebar_view = SidebarContainerView(subject, self) # Subject will be the main UiApp
        self.tabs_view = TabsView(subject, self) # Subject will be the main UiApp

    def open_buildin_tab(self, tab_name):
        self.tabs_view.open_buildin_tab(tab_name)

    def open_instance_tab(self, instance):
        self.tabs_view.open_instance_tab(instance)

    def open_agent_tab(self, agent):
        self.tabs_view.open_agent_tab(agent)
