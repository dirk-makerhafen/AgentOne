from server.models.agents.agent_version import AgentVersion
from ui.pyHtmlGui.pyhtmlgui.pyhtmlguiInstance import PyHtmlGuiInstance
from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_instance import AgentTaskInstance
from ui.pyHtmlGui.pyhtmlgui.view.querySetView import QuerySetView
import json

class AgentTaskDefinitionView(PyHtmlView):
    TEMPLATE_STR = """
    <div style='display:grid; grid-template-columns: repeat(13, auto);'>
        <div class="grid-cell">{{ pyview.subject.name }}, {{ pyview.subject.task_type }}</div>
        <div class="grid-cell">{{ pyview.subject.description }}</div>
        <div class="grid-cell">{{ pyview.subject.requires_approval }}</div>
        <div class="grid-cell">{{ pyview.subject.max_retries }}</div>
        <div class="grid-cell">{{ pyview.subject.retry_delay }}</div>
        <div class="grid-cell">{{ pyview.subject.max_concurrency }}</div>
        <div class="grid-cell">{{ pyview.subject.max_autonomous_steps }}</div>
        <div class="grid-cell">{{ pyview.subject.trigger }}</div>
        <div class="grid-cell">{{ pyview.subject.agent_task_instances.count() }}</div>
        <div class="grid-cell">{{ pyview.subject.agent_versions.count() }}</div>
    </div>
    """
    def __init__(self, subject, parent: PyHtmlView | PyHtmlGuiInstance, **kwargs):
        super().__init__(subject, parent, **kwargs)


class AgentTaskInstanceView(PyHtmlView):
    TEMPLATE_STR = """

    <div style='display:grid; grid-template-columns: repeat(5, auto);'>
        <div class="grid-cell">defname:{{ pyview.subject.agent_task_definition.name }}</div>
        <div class="grid-cell">Dep:{{ pyview.subject.taskinstance_arg_references.all()  }}</div>
        <div class="grid-cell">Success:{{ pyview.subject.taskinstance_sub_taskinstances.all()  }}</div>
        <div class="grid-cell">Err:{{ pyview.subject.taskinstances_on_error_callbacks.all()  }}</div>
        <div class="grid-cell">Sub:{{ pyview.subject.taskinstance_sub_taskinstances.all() }}</div>

    </div>
    """
    def __init__(self, subject, parent: PyHtmlView | PyHtmlGuiInstance, **kwargs):
        super().__init__(subject, parent, **kwargs)


class AgentTaskCallView(PyHtmlView):
    DOM_ELEMENT_CLASS = "node task-execution"
    TEMPLATE_STR = """
    <div class="node-wrapper {{ pyview.subject.status|lower }}">
        <div class="node-header">
            <span class="status-indicator"></span>
            <span class="name">#{{ pyview.subject.id }} {{ pyview.subject.agent_task_definition.name }}</span>
            <span class="detail">{{ pyview.subject.status_detail }}</span>
        </div>
        <div class="node-content">
            <div class="small-text meta">
                <i class="fas fa-clock"></i> {{ pyview.subject.created_at.strftime('%H:%M:%S') }} 
                {% if pyview.subject.retry_count > 0 %}<span class="badge bg-warning text-dark">Retry {{ pyview.subject.retry_count }}</span>{% endif %}
            </div>
            {% if pyview.subject.taskcall_arg_references.exists() %}
                <div class="dep-pills">
                    {% for dep in pyview.subject.taskcall_arg_references.all() %}
                        <span class="badge bg-secondary">from #{{ dep.id }}</span>
                    {% endfor %}
                </div>
            {% endif %}
        </div>

        {# Nested Sub-calls in the tree #}
        <div class="children">
            { { p yview.sub_calls_view.render() } }
        </div>
    </div>
    """
    def __init__(self, subject: AgentTaskCall, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        # In the sidebar, we show sub-calls generated via the run-hierarchy
        run = subject.taskcall_result_run
        '''
        subs =  AgentTaskCall.objects.filter(parent_relations__pk=run.pk) if run else AgentTaskCall.objects.none()
        self.sub_calls_view = QuerySetView(
            subject=subs, 
            parent=self, 
            item_class=AgentTaskCallView, 
            dom_element_class="tree-children"
        )'''
    

class TaskListView(PyHtmlView):
    TEMPLATE_STR = """
<style>


.mode-switch {
  position: sticky;
  top: 0;
  background: white;
  padding: 8px;
  border-bottom: 1px solid #ddd;
  display: flex;
  gap: 6px;
  z-index: 10;
}

.mode-switch button {
  padding: 4px 12px;
  border-radius: 6px;
  border: 1px solid #ccc;
  background: #f2f2f2;
  font-size: 12px;
  cursor: pointer;
}

.mode-switch button.active {
  background: #333;
  color: white;
}

.node {
  margin-left: 14px;
  padding-left: 12px;
  border-left: 2px solid #ddd;
  margin-top: 2px;
  background: #fff;
  border-radius: 6px;
  padding: 0px;
}

.node-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
}

.toggle {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 12px;
}

.node-meta {
  font-size: 11px;
  font-weight: normal;
  color: #666;
}

.flag {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 6px;
}

.flag.immutable {
  background: #444;
  color: white;
}

.node-body {
  margin-left: 25px;
  margin-top: 0px;
  font-size: 12px;
}

.dep {
  font-size: 11px;
  display: inline-block;
  margin-right: 6px;
}

.dep.requires {
  color: #555;
}

.dep.success {
  color: #1e7f43;
}

.dep.error {
  color: #a12020;
}

.status {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 6px;
}

.status.running {
  background: #fff6e5;
  color: #9a6a00;
  animation: pulse 1.4s infinite;
}

.status.success {
  background: #e6f8ec;
  color: #1e7f43;
}

.status.error {
  background: #fdeaea;
  color: #a12020;
}

@keyframes pulse {
  0% { opacity: 0.6; }
  50% { opacity: 1; }
  100% { opacity: 0.6; }
}

.children {
  margin-top: 6px;
}


</style>

        <b>Task Calls</b><br>
        {{ pyview.agent_task_calls_view.render() }}

        <b>Task Definition</b><br>
        {{ pyview.task_definitions_view.render() }}

        <b>Task Instances</b><br>
        {{ pyview.agent_task_instances_view.render() }}

    """
    
    def __init__(self, subject:AgentVersion, parent: PyHtmlView | PyHtmlGuiInstance, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.task_definitions_view = QuerySetView(subject=subject.agent_version.task_definitions, parent=self, item_class=AgentTaskDefinitionView)
        self.agent_task_instances_view = QuerySetView(subject=subject.agent_task_instances, parent=self, item_class=AgentTaskInstanceView)
        self.agent_task_calls_view = QuerySetView(subject=subject.agent_task_calls.order_by("-id")[:20], parent=self, item_class=AgentTaskCallView)

    def handle_approve(self, call_id):
        self.subject.task_dispatcher.approve_task(call_id)
        self.update()
