from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView

class TabToolsView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="tab-content active">
        <div class="sidebar-list-header">
            <span>Tool Registry</span>
            <button class="btn btn-xs btn-default" onclick="pyview.add_tool()"><i class="fa fa-plus"></i></button>
        </div>
        <table class="table table-hover">
            <thead>
                <tr><th>Tool Name</th><th>Type</th><th>Version</th><th>Status</th><th>Mode</th><th>Description</th><th>Enabled</th><th>Actions</th></tr>
            </thead>
            <tbody>
                {% for tool in pyview.subject.tools %}
                <tr>
                    <td>{{ tool.display_name }} ({{ tool.name }})</td>
                    <td>{{ 'Built-in' if tool.is_builtin else 'External' }}</td>
                    <td>{{ tool.manifest_version }}</td>
                    <td>{{ tool.status }}</td>
                    <td>{{ tool.execution_mode }}</td>
                    <td style="max-width:300px">{{ tool.description }}</td>
                    <td><label class="switch"><input type="checkbox" {{ 'checked' if tool.is_active else '' }}><span class="slider round"></span></label></td>
                    <td><button class="btn btn-xs btn-danger"><i class="fa fa-trash"></i></button></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    """
    def add_tool(self): pass
