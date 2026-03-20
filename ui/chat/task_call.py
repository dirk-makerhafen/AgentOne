
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_run import AgentTaskRun
from server.models.base_model import load_model_references, load_results_data
from ui.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
import json

from ui.pyHtmlGui.pyhtmlgui.view.queryset_view import QuerySetView


class TaskRunViewDetails(PyHtmlView):
    #DOM_ELEMENT_CLASS = "MessageView conversation-log-item log-type-tool tool-log-item"
    DOM_ELEMENT_CLASS = "task-run-details-item"
    TEMPLATE_STR = '''
    <div class="task-payload">
        <div class="payload-section">
            <div class="children-divider">Input Arguments</div>
            <div style="display: flex;">
                <div class="dep-list">
                    {% for dep in pyview.subject.taskrun_arg_references.all() %}
                        <div style="width:-webkit-fill-available">
                            <small> 
                                <p style="display:none">
                                    {{ dep.agent_instance.agent.name }} 
                                v{{ dep.agent_instance_version.agent_version.version_number }}   
                                i{{ dep.agent_instance.pk }} 
                                {{ dep.agent_task_definition.name }}
                                </p>
                                {{dep.__class__.__name__}}:#{{dep.pk}}
                            </small>
                        </div>
                    {% endfor %}
                </div>
                <div style="display:flex;flex-direction: column;width:-webkit-fill-available">
                    <div style="display: flex;flex-direction: row;    margin-left: auto;">
                        <button class="btn-small" style="z-index:1" onclick='document.getElementById("raw_arguments_json_{{pyview.uid}}").style.display="block"; document.getElementById("resolved_arguments_json_{{pyview.uid}}").style.display="none"'>raw</button> 
                        <button class="btn-small" style="z-index:1" onclick='document.getElementById("raw_arguments_json_{{pyview.uid}}").style.display="none"; document.getElementById("resolved_arguments_json_{{pyview.uid}}").style.display="block"'>resolved</button>
                    </div>  

                    <div style="width:-webkit-fill-available;margin-top:-30px">
                        <div class="raw_arguments_json debug-json" id="raw_arguments_json_{{pyview.uid}}" style="display:none">
                            {{ pyview.subject.arguments_json }}
                        </div>
                        <div class="resolved_arguments_json debug-json" id="resolved_arguments_json_{{pyview.uid}}">
                            {{ pyview.resolved_arguments()}}
                        </div>
            
                    </div>
                </div>  
            </div>
        </div>

        ResultJson:{{ pyview.subject.result_json }}

    </div>

    '''


    def resolved_arguments(self):
        args, _ = load_model_references(self.subject.arguments_json)
        args = load_results_data(args, timeout=0)
        return args


class TaskRunView(PyHtmlView):
    #DOM_ELEMENT_CLASS = "MessageView conversation-log-item log-type-tool tool-log-item"
    DOM_ELEMENT_CLASS = "task-run-item"
    TEMPLATE_STR = """    
    <div class="task-node task-node-run  {{ 'is-subtask' if pyview.is_subtask }}">
        <div class="task-header" onclick="pyview.toggle_details()">
            <div class="task-io">
                <div class="arguments">ARGUMENTS
                </div>
                <div  class="result  {{ 'hidden' if not pyview.is_details_hidden else '' }}">RESULT
                </div>
            </div>

            <div class="task-icon">
                {% if pyview.subject.agent_task_definition.task_type == 'CHAIN' %}
                    <i class="fas fa-link" title="Chain"></i>
                {% elif pyview.subject.agent_task_definition.task_type == 'GROUP' %}
                    <i class="fas fa-layer-group" title="Group"></i>
                {% elif pyview.subject.agent_task_definition.task_type == 'TOOL' %}
                    <i class="fas fa-wrench" title="Tool"></i>
                {% else %}
                    <i class="fas fa-terminal" title="Task"></i>
                {% endif %}
            </div>
            
            <div class="task-info">
                <span class="task-name">
                    {{ pyview.subject.agent_instance.agent.name }} 
                    v{{ pyview.subject.agent_instance_version.agent_version.version_number }} 
                    i{{ pyview.subject.agent_instance.pk }} 
                    {{ pyview.subject.agent_task_definition.name }}
                    TaskInstance:#{{ pyview.subject.agent_task_instance.pk }}
                    TaskCall:#{{ pyview.subject.agent_task_call.id }}
                    TaskRun:#{{ pyview.subject.id }}
                </span>
                <span class="task-statusbadge">{{ pyview.subject.status }}</span>
            </div>

            <div class="task-meta">
                {% if pyview.subject.taskrun_arg_references.exists() %}
                    <span class="badge bg-info"><i class="fas fa-sign-in-alt"></i> {{ pyview.subject.taskrun_arg_references.count() }} deps</span>
                {% endif %}
                <small class="text-muted">{{ pyview.subject.created_at.strftime('%H:%M:%S') }}</small>
            </div>
        </div>

        <div class="task-details {{ 'hidden' if pyview.is_details_hidden else '' }}">
            {% if not pyview.is_details_hidden %}
                {{ pyview.details_view.render() }}
            {% endif %}
        </div>
    </div>
    <div class="task-children">
        <div class="children-divider">Sub-tasks generated by {{ pyview.subject.agent_task_definition.task_type }}</div>
        {{ pyview.taskrun_subtask_reference_views.render() }}
    </div>

    <div class="task-children">
        <div class="children-divider">Result References</div>
        {{ pyview.taskrun_result_references_views.render() }}
    </div>
                
    """
    @property
    def DOM_ELEMENT_EXTRAS(self):
        return f'style="order: {int(self.subject.created_at.timestamp())}"'

    def __init__(self, subject: AgentTaskRun, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.s = subject
        self.is_details_hidden = True
        self.is_subtask = kwargs.get('is_subtask', False)
        self.taskrun_subtask_reference_views = QuerySetView(subject=subject.taskrun_subtask_references, parent=self, item_class=TaskCallView)
        self.taskrun_result_references_views = QuerySetView(subject=subject.taskrun_result_references, parent=self, item_class=TaskCallView)
        self.details_view = None


    def toggle_details(self):
        self.is_details_hidden = not self.is_details_hidden
        if self.is_details_hidden:
            self.details_view = None
        else:
            self.details_view = TaskRunViewDetails(subject=self.s, parent=self)
        self.update()

    def get_formatted_args(self):
        # Merge instance and call args for the dev view
        return json.dumps(self.s.arguments_json.get("*",[]), indent=2)
    def get_formatted_kwargs(self):
        # Merge instance and call args for the dev view
        return {k:json.dumps(v, indent=2) for k,v in self.s.arguments_json.items() if k != "*"}




class TaskCasllPayLoadView(PyHtmlView):
    TEMPLATE_STR = '''
        <div class="task-payload">

            <div class="payload-section">
                <div class="children-divider">Input Arguments</div>
                <div style="    display: flex;">
                    <div class="dep-list">
                        {% for dep in pyview.subject.taskcall_arg_references.all() %}
                            <div style="width:-webkit-fill-available">
                                <small> 
                                    <p style="display:none">
                                        {{ dep.agent_instance.agent.name }} 
                                        v{{ dep.agent_instance_version.agent_version.version_number }}   
                                        i{{ dep.agent_instance.pk }} 
                                        {{ dep.agent_task_definition.name }}   
                                    </p>
                                    {{dep.__class__.__name__}}:#{{dep.pk}}
                    
                                </small>
                            </div>
                        {% endfor %}
                    </div>
                    <div style="display:flex;flex-direction: column;width:-webkit-fill-available">
                        <div style="display: flex;flex-direction: row;    margin-left: auto;">
                            <button class="btn-small" style="z-index:1" onclick='document.getElementById("raw_arguments_json_{{pyview.uid}}").style.display="none"; document.getElementById("resolved_arguments_json_{{pyview.uid}}").style.display="block"'>raw</button>
                            <button class="btn-small" style="z-index:1" onclick='document.getElementById("raw_arguments_json_{{pyview.uid}}").style.display="block"; document.getElementById("resolved_arguments_json_{{pyview.uid}}").style.display="none"'>resolved</button>
                        </div>
                        
                        <div  style="width:-webkit-fill-available;margin-top:-30px">
                            <div class="raw_arguments_json debug-json"  id="raw_arguments_json_{{pyview.uid}}" style="display:none">{{ pyview.subject.carguments_json }}</div>
                            <div class="resolved_arguments_json debug-json"  id="resolved_arguments_json_{{pyview.uid}}">{{ pyview.subject.carguments_json }}</div>
                        </div>
                    </div>
                    
                </div>
            </div>

            <div class="task-children">
                <div class="children-divider">Before Call Hooks</div>
                {{ pyview.before_call_hook_views.render() }}
            </div>
            
            <div class="task-children">
                <div class="children-divider">Runs</div>
                {{pyview.subject.related_agent_task_runs.all()}}
                {{ pyview.run_views.render() }}
            </div>
            
            <div class="task-children">
                <div class="children-divider">After Call Hooks</div>
                    {{pyview.after_call_hook_views.render() }}
            </div>

            <div class="task-children">
                <div class="children-divider">Result Task</div>
                    {{pyview.subject.taskcall_result_run }}
            </div>

            <br>on success {{pyview.subject.taskcall_on_success_callbacks.all() }} 
            <br>on error {{pyview.subject.taskcall_on_error_callbacks.all()  }}

        </div>
    '''

    def __init__(self, subject: AgentTaskCall, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.s = subject
        self.run_views = QuerySetView(subject=subject.related_agent_task_runs, parent=self, item_class=TaskRunView)
        self.before_call_hook_views = QuerySetView(subject=subject.taskcall_before_run_hooks, parent=self, item_class=TaskCallView)
        self.after_call_hook_views = QuerySetView(subject=subject.taskcall_after_run_hooks, parent=self, item_class=TaskCallView)


class TaskCallView(PyHtmlView):
    #DOM_ELEMENT_CLASS = "MessageView conversation-log-item log-type-tool tool-log-item"
    DOM_ELEMENT_CLASS = "task-call-item"
    TEMPLATE_STR = """

<style>
.task-node {
    border: 1px solid #ddd;
    border-radius: 4px;
    margin-bottom: 2px;
    background: #f8f9fa;
    transition: all 0.2s;
    border-left: 3px solid #007bff;
}

.task-node-run {
    border-left: 3px solid #ff7b76;
}

.task-node.is-subtask {
    margin-left: 20px;
    border-left: 3px solid #007bff;
}

.task-io {
    font-size: 50%;
}

.task-header {
    display: flex;
    padding: 0px 12px;
    cursor: pointer;
    align-items: center;
}

.task-header:hover {
    background: #e9ecef;
}

.task-icon {
    width: 24px;
    color: #6c757d;
}

.task-info {
    flex-grow: 1;
}

.task-name {
    #font-weight: bold;
    #font-family: 'Fira Code', monospace;
}

.task-id {
    font-size: 0.8em;
    color: #888;
    margin-left: 5px;
}

.task-statusbadge {
    font-size: 0.75em;
    padding: 2px 6px;
    border-radius: 10px;
    background: #eee;
    margin-left: 10px;
}

.status-ended_success .task-statusbadge { background: #d4edda; color: #155724; }
.status-ended_failure_exception .task-statusbadge { background: #f8d7da; color: #721c24; }
.status-active_running .task-statusbadge { background: #fff3cd; color: #856404; font-weight: bold; }

.task-payload {
    padding: 10px;
    background: #fff;
    border-top: 1px solid #eee;
}

.debug-json {
    font-size: 11px;
    background: #272822;
    color: #f8f8f2;
    padding: 8px;
    border-radius: 3px;
    max-height: 200px;
    overflow-y: auto;
    margin-left: 10px;

}

.children-divider {
    font-size: 10px;
    text-transform: uppercase;
    color: #888;
    padding: 5px 3px;
    letter-spacing: 1px;
}
</style>





    
    <div class="task-node status-{{ pyview.subject.status|lower }} {{ 'is-subtask' if pyview.is_subtask }}">
        <div class="task-header" onclick="pyview.toggle_details()">
            {% if pyview.subject.status == "NEW" %}
                <button onclick="pyview.subject.apply_async()">start now</button>
            {% endif %}
            {% if pyview.subject.status_detail == "WAITING_RETRY" %}
                <button onclick="pyview.subject.apply_async()">start now</button>
            {% endif %}
            <div class="task-io">
                <div class="arguments">ARGUMENTS
                </div>
                <div class="result  {{ 'hidden' if not pyview.is_details_hidden else '' }}">RESULT
                </div>
            </div>

            <div class="task-icon">
                {% if pyview.subject.agent_task_definition.task_type == 'CHAIN' %}
                    <i class="fas fa-link" title="Chain"></i>
                {% elif pyview.subject.agent_task_definition.task_type == 'GROUP' %}
                    <i class="fas fa-layer-group" title="Group"></i>
                {% elif pyview.subject.agent_task_definition.task_type == 'TOOL' %}
                    <i class="fas fa-wrench" title="Tool"></i>
                {% else %}
                    <i class="fas fa-terminal" title="Task"></i>
                {% endif %}
            </div>
            

            <div class="task-info">
                <span class="task-name">
                    {{ pyview.subject.agent_instance.agent.name }} 
                    v{{ pyview.subject.agent_instance_version.agent_version.version_number }} 
                    i{{ pyview.subject.agent_instance.pk }} 
                    {{ pyview.subject.agent_task_definition.name }}
                    TaskInstance:#{{ pyview.subject.agent_task_instance.pk }}
                    TaskCall:#{{ pyview.subject.id }}
                </span>
                <span class="task-statusbadge">{{ pyview.subject.status_detail }}</span>
            </div>

            <div class="task-meta">
                {% if pyview.subject.taskcall_arg_references.exists() %}
                    <span class="badge bg-info"><i class="fas fa-sign-in-alt"></i> {{ pyview.subject.taskcall_arg_references.count() }} deps</span>
                {% endif %}
                <small class="text-muted">{{ pyview.subject.created_at.strftime('%H:%M:%S') }}</small>
            </div>
        </div>

        <div class="task-details {{ 'hidden' if pyview.is_details_hidden else '' }}">
           {% if not pyview.is_details_hidden %}
                {{ pyview.task_call_view_payload.render() }}
           {% endif %}
        </div>
    </div>
    """
    @property
    def DOM_ELEMENT_EXTRAS(self):
        return f'style="order: {int(self.subject.created_at.timestamp())}"'

    def __init__(self, subject: AgentTaskCall, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.s = subject
        self.is_details_hidden = True
        self.is_subtask = kwargs.get('is_subtask', False)
        self.task_call_view_payload = None

    def toggle_details(self):
        self.is_details_hidden = not self.is_details_hidden
        if self.is_details_hidden:
            self.task_call_view_payload = None
        else:
            self.task_call_view_payload = TaskCasllPayLoadView(subject=self.s, parent=self )
        self.update()

    def get_formatted_args(self):
        # Merge instance and call args for the dev view
        return json.dumps(self.subject.carguments_json, indent=2)
