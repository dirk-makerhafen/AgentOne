from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView

class SidebarEventsView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="agent-events-container sidebar-content-area">
        <div class="event-section">
            <h6>Receiver Functions</h6>
            <p class="small text-muted">Functions on this instance that can be triggered by events.</p>
            <button type="button" class="btn btn-xs btn-success" onclick="pyview.render_instance_event_receiver_form()">
                <i class="fa fa-plus"></i> New Receiver
            </button>
            <div id="instance-event-receivers-list_{{ pyview.subject.instance_pk }}" class="sidebar-list">
                {% for receiver in pyview.subject.receivers %}
                    {{ pyview.render_receiver(receiver) }}
                {% endfor %}
            </div>
            <div id="instance-event-receiver-form-container_{{ pyview.subject.instance_pk }}">
                {% if pyview.show_receiver_form %}
                    {{ pyview.render_receiver_form() }}
                {% endif %}
            </div>
        </div>
        <div class="event-section">
            <h6>Event Assignments</h6>
            <p class="small text-muted">Events this instance is subscribed to.</p>
            <button type="button" class="btn btn-xs btn-success" onclick="pyview.render_instance_event_subscription_form()">
                <i class="fa fa-plus"></i> New Assignment
            </button>
            <div id="instance-event-assignments-list_{{ pyview.subject.instance_pk }}" class="sidebar-list">
                {% for assignment in pyview.subject.assignments %}
                    {{ pyview.render_assignment(assignment) }}
                {% endfor %}
            </div>
            <div id="instance-event-assignment-form-container_{{ pyview.subject.instance_pk }}">
                {% if pyview.show_assignment_form %}
                    {{ pyview.render_assignment_form() }}
                {% endif %}
            </div>
        </div>
    </div>
    """

    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.show_receiver_form = False
        self.show_assignment_form = False
        self._receiver_views = {}
        self._assignment_views = {}

    def render_receiver(self, receiver):
        if receiver.id not in self._receiver_views:
            self._receiver_views[receiver.id] = SidebarEventReceiverItemView(receiver, self, instance_pk=self.subject.instance_pk)
        return self._receiver_views[receiver.id].render()

    def render_assignment(self, assignment):
        if assignment.id not in self._assignment_views:
            self._assignment_views[assignment.id] = SidebarEventAssignmentItemView(assignment, self, instance_pk=self.subject.instance_pk)
        return self._assignment_views[assignment.id].render()

    def render_instance_event_receiver_form(self, receiver_id=None): 
        self.show_receiver_form = True
        self.update()

    def render_instance_event_subscription_form(self, assignment_id=None): 
        self.show_assignment_form = True
        self.update()

class SidebarEventReceiverItemView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="list-item">
        <strong>{{ pyview.subject.name }}</strong>
        <p class="small text-muted">Event: <code>{{ pyview.subject.event }}</code></p>
        <div class="item-actions">
            <button type="button" class="btn btn-xs btn-primary" onclick="pyview.edit_receiver()">Edit</button>
            <button type="button" class="btn btn-xs btn-danger" onclick="pyview.delete_receiver()">Delete</button>
        </div>
    </div>
    """
    def __init__(self, subject, parent, instance_pk, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.instance_pk = instance_pk
    def edit_receiver(self): 
        self.parent.render_instance_event_receiver_form(self.subject.id)
    def delete_receiver(self): pass

class SidebarEventAssignmentItemView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="list-item">
        <p>Subscribed to <strong>{{ pyview.subject.eventHandler.name }}</strong></p>
        <div class="item-actions">
            <button type="button" class="btn btn-xs btn-primary" onclick="pyview.edit_assignment()">Edit</button>
            <button type="button" class="btn btn-xs btn-danger" onclick="pyview.delete_assignment()">Delete</button>
        </div>
    </div>
    """
    def __init__(self, subject, parent, instance_pk, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.instance_pk = instance_pk
    def edit_assignment(self): 
        self.parent.render_instance_event_subscription_form(self.subject.id)
    def delete_assignment(self): pass

class SidebarEventReceiverFormView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="sub-form-container sidebar-form">
        <h6>{% if pyview.subject.receiver and pyview.subject.receiver.id %}Edit{% else %}Create{% endif %} Receiver</h6>
        <div id="instance-event-receiver-form-{{ pyview.subject.instance_pk }}">
            <input type="hidden" name="id" value="{{ pyview.subject.receiver.id }}">
            <div class="form-group">
                <label>Name</label>
                <input type="text" class="form-control input-sm" name="name" value="{{ pyview.subject.receiver.name }}" required>
            </div>
            <div class="form-group">
                <label>Description</label>
                <textarea class="form-control input-sm" name="description">{{ pyview.subject.receiver.description }}</textarea>
            </div>
            <div class="form-group">
                <label>Event Type</label>
                <select class="form-control input-sm" name="event">
                    <option value="event_agentinstance_created" {{ 'selected' if pyview.subject.receiver.event == 'event_agentinstance_created' else '' }}>event_agentinstance_created(agent, agentInstance)</option>
                    <option value="event_conversationMessage_added" {{ 'selected' if pyview.subject.receiver.event == 'event_conversationMessage_added' else '' }}>event_conversationMessage_added(agent, agentInstance, conversationMessage)</option>
                    <option value="event_llmquery_pre_execute" {{ 'selected' if pyview.subject.receiver.event == 'event_llmquery_pre_execute' else '' }}>event_llmquery_pre_execute(agent, agentInstance, llmQuery)</option>
                    <option value="event_llmquery_successfull" {{ 'selected' if pyview.subject.receiver.event == 'event_llmquery_successfull' else '' }}>event_llmquery_successfull(..., llmQuery, llmResponse, conversationMessage)</option>
                    <option value="event_llmquery_failed" {{ 'selected' if pyview.subject.receiver.event == 'event_llmquery_failed' else '' }}>event_llmquery_failed(llmQuery, llmResponse, conversationMessage)</option>
                    <option value="event_llmresponse_pre_parse" {{ 'selected' if pyview.subject.receiver.event == 'event_llmresponse_pre_parse' else '' }}>event_llmresponse_pre_parse(..., response_string_full)</option>
                    <option value="event_llmresponse_post_parse" {{ 'selected' if pyview.subject.receiver.event == 'event_llmresponse_post_parse' else '' }}>event_llmresponse_post_parse(..., response_string_full, parts)</option>
                    <option value="event_llmresponse_pre_tool_calls" {{ 'selected' if pyview.subject.receiver.event == 'event_llmresponse_pre_tool_calls' else '' }}>event_llmresponse_pre_tool_calls(..., conversationMessage, toolcalls)</option>
                    <option value="event_llmresponse_pre_tool_call" {{ 'selected' if pyview.subject.receiver.event == 'event_llmresponse_pre_tool_call' else '' }}>event_llmresponse_pre_tool_call(..., conversationMessage, toolcall)</option>
                    <option value="event_llmresponse_post_tool_call" {{ 'selected' if pyview.subject.receiver.event == 'event_llmresponse_post_tool_call' else '' }}>event_llmresponse_post_tool_call(..., conversationMessage, toolcall)</option>
                    <option value="event_llmresponse_post_tool_calls" {{ 'selected' if pyview.subject.receiver.event == 'event_llmresponse_post_tool_calls' else '' }}>event_llmresponse_post_tool_calls(..., conversationMessage, toolcalls)</option>
                    <option value="event_llmresponse_finished" {{ 'selected' if pyview.subject.receiver.event == 'event_llmresponse_finished' else '' }}>event_llmresponse_finished(llmQuery, llmResponse, conversationMessage)</option>
                </select>
            </div>
            <div class="form-group">
                <label>Source Code</label>
                <textarea class="form-control input-sm" name="source" rows="4">{{ pyview.subject.receiver.source }}</textarea>
            </div>
            <div class="checkbox">
                <label><input type="checkbox" name="is_public" {{ 'checked' if pyview.subject.receiver.is_public else '' }}> Is Public</label>
            </div>
            <div class="checkbox">
                <label><input type="checkbox" name="enabled" {{ 'checked' if pyview.subject.receiver.enabled else '' }}> Enabled</label>
            </div>
            <div class="form-actions">
                <button type="button" id="save-instance-receiver-btn-{{ pyview.subject.instance_pk }}" class="btn btn-xs btn-primary">Save</button>
                <button type="button" class="btn btn-xs btn-default" onclick="pyview.close_form()">Cancel</button>
            </div>
        </div>
    </div>
    """
    def close_form(self): 
        self.parent.show_receiver_form = False
        self.parent.update()

class SidebarEventAssignmentFormView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="sub-form-container sidebar-form">
        <h6>{% if pyview.subject.assignment and pyview.subject.assignment.id %}Edit{% else %}Create{% endif %} Assignment</h6>
        <div id="instance-event-assignment-form-{{ pyview.subject.instance_pk }}">
            <input type="hidden" name="id" value="{{ pyview.subject.assignment.id }}">
            <div class="form-group">
                <label>Description</label>
                <textarea class="form-control input-sm" name="description">{{ pyview.subject.assignment.description }}</textarea>
            </div>
            <div class="form-group">
                <label>Receiver Function</label>
                <select class="form-control input-sm" name="eventHandler_id">
                    {% for receiver in pyview.subject.publicReceivers %}
                        <option value="{{ receiver.id }}" {{ 'selected' if receiver.id == pyview.subject.assignment.eventHandler.id else '' }}>{{ receiver.name }} (by {{ receiver.agent.name }})</option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-actions">
                <button type="button" id="save-instance-assignment-btn-{{ pyview.subject.instance_pk }}" class="btn btn-xs btn-primary">Save</button>
                <button type="button" class="btn btn-xs btn-default" onclick="pyview.close_form()">Cancel</button>
            </div>
        </div>
    </div>
    """
    def close_form(self): 
        self.parent.show_assignment_form = False
        self.parent.update()

