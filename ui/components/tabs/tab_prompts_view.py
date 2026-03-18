from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView


class TabPromptsView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="tab-content active">
        <div class="sidebar-list-header">
            <span>Prompts</span>
            <button class="btn btn-xs btn-default" onclick="pyview.toggle_add_form()"><i class="fa fa-plus"></i></button>
        </div>
        {% if pyview.show_add_form %}
        <div id="add-prompt-form-container" class="add-prompt-form" style="padding:15px; background: #f9f9f9; border-bottom: 1px solid #ddd;">
            <h4>Create New Prompt Template</h4>
            <div class="row">
                <div class="col-md-2">
                    <label>Source</label>
                    <input type="text" class="form-control" placeholder="e.g., agents" id="new_prompt_source">
                </div>
                <div class="col-md-2">
                    <label>Key</label>
                    <input type="text" class="form-control" placeholder="e.g., System" id="new_prompt_key">
                </div>
                <div class="col-md-8">
                    <label>Description</label>
                    <textarea class="form-control" placeholder="Description" id="new_prompt_desc"></textarea>
                </div>
                <div class="col-md-12" style="margin-top:10px">
                    <label>Initial Value</label>
                    <textarea class="form-control" rows="5" placeholder="Enter content..." id="new_prompt_val"></textarea>
                </div>
            </div>
            <div class="form-buttons" style="margin-top:10px">
                <button class="btn btn-success" onclick="pyview.save_prompt()">Save Prompt</button>
                <button class="btn btn-default" onclick="pyview.toggle_add_form()">Cancel</button>
            </div>
        </div>
        {% endif %}
        <table class="table table-hover prompts-table">
            <thead>
                <tr><th></th><th>Source</th><th>Key</th><th>Description</th><th>Variants</th><th>Actions</th></tr>
            </thead>
            <tbody>
                {% for prompt in pyview.subject.prompts %}
                    <tr class="prompt-definition-row">
                        <td><i class="fa fa-chevron-right"></i></td>
                        <td><strong>{{ prompt.source }}</strong></td>
                        <td><strong>{{ prompt.key }}</strong></td>
                        <td>{{ prompt.description }}</td>
                        <td><span class="badge">{{ prompt.variants_count }}</span></td>
                        <td><button class="btn btn-xs btn-danger"><i class="fa fa-trash"></i></button></td>
                    </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    """
    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.show_add_form = False

    def toggle_add_form(self):
        self.show_add_form = not self.show_add_form
        self.update()

    def save_prompt(self):
        pass
