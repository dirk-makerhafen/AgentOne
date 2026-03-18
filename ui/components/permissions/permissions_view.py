from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView

class PermissionMatrixRowView(PyHtmlView):
    TEMPLATE_STR = """
    <tr id="perm-row-{{ pyview.subject.target_instance_pk }}_{{ pyview.instancePk }}">
        <td class="agent-name-cell">{{ pyview.subject.target_instance_name }}</td>
        <td class="permission-checkbox-cell">
            <input type="checkbox" data-target-pk="{{ pyview.subject.target_instance_pk }}" data-permission-type="can_send" {{ 'checked' if pyview.subject.can_send else '' }} onchange="pyview.handle_permission_change(this)">
        </td>
        <td class="permission-checkbox-cell">
            <input type="checkbox" data-target-pk="{{ pyview.subject.target_instance_pk }}" data-permission-type="can_receive" {{ 'checked' if pyview.subject.can_receive else '' }} onchange="pyview.handle_permission_change(this)">
        </td>
        <td class="actions-cell">
            <button class="remove-permission-btn" title="Remove from matrix" onclick="pyview.remove_instance_from_matrix()">
                <i class="fa fa-trash-o"></i>
            </button>
        </td>
    </tr>
    """
    def __init__(self, subject, parent, instancePk, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.instancePk = instancePk

    def handle_permission_change(self, element): pass
    def remove_instance_from_matrix(self): pass


class SidebarPermissionsView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="permissions-container" id="permissions-container_{{ pyview.subject.instancePk }}">
        <h4>Outbound Permissions</h4>
        <p class="text-muted"><small>Define which agents this instance can communicate with.</small></p>

        <div class="permission-search-container">
            <input type="text" id="permission-search-input_{{ pyview.subject.instancePk }}" onkeyup="pyview.filter_available_instances(this.value)" placeholder="Search agents to add to matrix...">
            <div id="permission-search-results_{{ pyview.subject.instancePk }}">
                {% for result in pyview.subject.search_results %}
                    {{ pyview.render_search_result(result) }}
                {% endfor %}
            </div>
        </div>

        <div class="permissions-matrix-container">
            {% if pyview.subject.outbound_permissions %}
            <table class="permissions-matrix" id="permissions-matrix-table_{{ pyview.subject.instancePk }}">
                <thead>
                    <tr>
                        <th>Target Agent</th>
                        <th class="permission-checkbox-cell">Can Send</th>
                        <th class="permission-checkbox-cell">Can Receive</th>
                        <th class="actions-cell">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for perm in pyview.subject.outbound_permissions %}
                        {{ pyview.render_outbound_permission(perm) }}
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
                <div id="permissions-empty-state_{{ pyview.subject.instancePk }}" class="permissions-empty-state">
                    <p>No outbound permissions configured.</p>
                    <p><small>Use the search bar above to find and add agents to the matrix.</small></p>
                </div>
            {% endif %}
        </div>
        <hr class="permission-divider"/>
        <h4>Inbound Permissions</h4>
        <p class="text-muted"><small>Shows which agents have permission to communicate with this instance.</small></p>
        <div class="permissions-matrix-container">
            {% if pyview.subject.inbound_permissions %}
            <table class="permissions-matrix readonly">
                <thead>
                    <tr>
                        <th>Source Agent</th>
                        <th class="permission-checkbox-cell">Can Send to Me</th>
                        <th class="permission-checkbox-cell">Can Receive from Me</th>
                    </tr>
                </thead>
                <tbody>
                    {% for perm in pyview.subject.inbound_permissions %}
                        {{ pyview.render_inbound_permission(perm) }}
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
                <div class="permissions-empty-state">
                    <p>No other agents have permissions configured for this instance.</p>
                </div>
            {% endif %}
        </div>
    </div>
    """
    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._search_result_views = {}
        self._outbound_perm_views = {}
        self._inbound_perm_views = {}

    def render_search_result(self, result):
        if result.target_instance_pk not in self._search_result_views:
            self._search_result_views[result.target_instance_pk] = SearchResultItemView(result, self, instancePk=self.subject.instancePk)
        return self._search_result_views[result.target_instance_pk].render()

    def render_outbound_permission(self, perm):
        if perm.target_instance_pk not in self._outbound_perm_views:
            self._outbound_perm_views[perm.target_instance_pk] = PermissionMatrixRowView(perm, self, instancePk=self.subject.instancePk)
        return self._outbound_perm_views[perm.target_instance_pk].render()

    def render_inbound_permission(self, perm):
        # For inbound, no actions, just display
        return f"<tr><td class=\"agent-name-cell\">{perm.source_instance_name}</td>" \
               f"<td class=\"permission-checkbox-cell\"><i class=\"fa {'fa-check-square-o text-success' if perm.can_send else 'fa-square-o'}\"></i></td>" \
               f"<td class=\"permission-checkbox-cell\"><i class=\"fa {'fa-check-square-o text-success' if perm.can_receive else 'fa-square-o'}\"></i></td></tr>"

    def filter_available_instances(self, value): pass



class SearchResultItemView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="search-result-item">
        <div class="search-result-info">
            <div class="name">{{ pyview.subject.target_instance_name }}</div>
            <div class="description">{{ pyview.subject.target_instance_description if pyview.subject.target_instance_description else 'No description' }}</div>
        </div>
        <button class="add-permission-btn" onclick="pyview.add_instance_to_matrix()">Add</button>
    </div>
    """
    def __init__(self, subject, parent, instancePk, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.instancePk = instancePk

    def add_instance_to_matrix(self): pass
