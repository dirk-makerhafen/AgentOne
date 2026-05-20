from __future__ import annotations
from server.models.sessions.session import SessionModel
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_instance import AgentTaskInstance
from server.models.tasks.task_definition import TaskDefinition
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.lib.queryset_view import QuerySetView
from ui.lib.model_view import ModelView


class TaskDefinitionView(ModelView):
    """One-row summary of an TaskDefinition."""
    DOM_ELEMENT_CLASS = "TaskDefinitionView task-def-row"

    TEMPLATE_STR = """
        <div class="task-def-inner">
            <span class="task-def-name">{{ pyview.subject.name }}</span>
            <span class="task-def-type badge">{{ pyview.subject.task_type }}</span>
            <span class="task-def-desc text-muted small">{{ pyview.subject.description }}</span>
            <div class="task-def-meta small">
                approval={{ pyview.subject.requires_approval }}
                retries={{ pyview.subject.max_retries }}
                priority={{pyview.subject.priority}}
                delay={{ pyview.subject.retry_delay }}s
            </div>
        </div>
    """


class TaskInstanceView(ModelView):
    """One-row summary of an AgentTaskInstance."""
    DOM_ELEMENT_CLASS = "TaskInstanceView task-instance-row"

    TEMPLATE_STR = """
        <div class="task-instance-inner">
            <span class="task-def-name">{{ pyview.subject.agent_task_definition.name }}</span>
            <span class="text-muted small">
                deps={{ pyview.subject.taskinstance_arg_references.count() }}
                subtasks={{ pyview.subject.child_instances.count() }}
                on_success={{ pyview.subject.taskinstances_on_success_callbacks.count() }}
                on_error={{ pyview.subject.taskinstances_on_error_callbacks.count() }}
            </span>
        </div>
    """


class TaskCallRowView(ModelView):
    """
    Compact one-row view of an AgentTaskCall for the tasks panel.
    Not the full tree — use ui/chat/task_call.py TaskCallView for that.
    """
    DOM_ELEMENT_CLASS = "TaskCallRowView task-call-row"

    TEMPLATE_STR = """
        <div class="task-call-inner {{ pyview.subject.status_detail|lower|replace('_','-') }}">
            <span class="task-call-id text-muted">#{{ pyview.subject.id }}</span>
            <span class="task-call-name">{{ pyview.subject.agent_task_definition.name }}</span>
            <span class="task-call-status badge">{{ pyview.subject.status_detail }}</span>
            {% if pyview.subject.retry_count > 0 %}
                <span class="badge badge--warning">retry {{ pyview.subject.retry_count }}</span>
            {% endif %}
            <span class="task-call-time text-muted small">
                {{ pyview.subject.created_at.strftime('%H:%M:%S') }}
            </span>
            {% if pyview.subject.taskcall_arg_references.exists() %}
                <span class="text-muted small">
                    deps:
                    {% for dep in pyview.subject.taskcall_arg_references.all() %}
                        #{{ dep.id }}
                    {% endfor %}
                </span>
            {% endif %}
        </div>
    """


class TasksPanelView(ModelView):
    """
    Right-panel tasks view for an AgentInstance.
    Shows recent task calls, task definitions, and task instances.
    Subject is AgentInstance.
    """
    DOM_ELEMENT_CLASS = "TasksPanelView"

    TEMPLATE_STR = """
        <div class="panel-section">
            <div class="panel-section-header">Commands</div>
            {{ pyview.commands_view.render() }}
        </div>
        
        <div class="panel-section">
            <div class="panel-section-header">Tools</div>
            {{ pyview.tools_view.render() }}
        </div>
        
        <div class="panel-section">
            <div class="panel-section-header">Tasks</div>
            {{ pyview.tasks_view.render() }}
        </div>
        
        <div class="panel-section">
            <div class="panel-section-header">Skills</div>
            {{ pyview.skills_view.render() }}
        </div>      

        <div class="panel-section">
            <div class="panel-section-header">
                Recent task calls
                <span class="text-muted small">(last 20)</span>
            </div>
            
        </div>
    """
    CSS_STR = '''
        .panel-section-header {
            font-weight: bold;
        }
    '''
    def __init__(self, subject: SessionModel, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        '''
        {{ pyview.task_calls_view.render() }}
        self.task_calls_view = QuerySetView(
            subject=subject.agent_task_calls.order_by("-id")[:20],
            parent=self,
            item_class=TaskCallRowView,
        )
        '''
        self.tasks_view = QuerySetView(
            subject=subject.latest_session_version.agent_version.tasks(),
            parent=self,
            item_class=TaskDefinitionView,
        )
        self.commands_view = QuerySetView(
            subject=subject.latest_session_version.agent_version.commands(),
            parent=self,
            item_class=TaskDefinitionView,
        )
        self.tools_view = QuerySetView(
            subject=subject.latest_session_version.agent_version.tools(),
            parent=self,
            item_class=TaskDefinitionView,
        )
        self.skills_view = QuerySetView(
            subject=subject.latest_session_version.agent_version.skills(),
            parent=self,
            item_class=TaskDefinitionView,
        )
        '''
        {{ pyview.task_instances_view.render() }}
        self.task_instances_view = QuerySetView(
            subject=subject.agent_task_instances.all(),
            parent=self,
            item_class=TaskInstanceView,
        )
        '''

    def approve(self, call_id: int):
        from runtime.tasks.call_scheduler import CallScheduler
        CallScheduler.approve_taskcall(call_id)
        self.update()