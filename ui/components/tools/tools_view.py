from server.models.agents.agent_version import AgentVersion, AgentVersionAvailableTool
from ui.pyHtmlGui.pyhtmlgui.pyhtmlguiInstance import PyHtmlGuiInstance
from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_instance import AgentTaskInstance
from ui.pyHtmlGui.pyhtmlgui.view.querySetView import QuerySetView
import json

'''


    # Options - Run
    time_limit      = models.IntegerField(default=None, null=True)     #   
    max_subtask_errors     = models.IntegerField(default=0)   # for groups,absolute number, also used when timeout
    max_subtask_error_rate = models.IntegerField(default=0)# for groups, in percent, also used when timeout
    limit_subtask_parallel_runs  = models.IntegerField(default=0) # how many subtasks cn run in parallel, for groups 0=no limit
    limit_per_instance_parallel_runs  = models.IntegerField(default=1) #how many times this task can run in parallel per agentInstance it belongs to, 0=no limit

    # Options - Retry
    max_retries  = models.IntegerField(default=0)   # how many retries to we make in case of error
    retry_delay  = models.IntegerField(default=0)  # time between retries in seconds
    retry_requires_approval = models.BooleanField(default=True)  # required user approval before run

    trigger = models.CharField(max_length=255, default=None, blank=True, null=True)

'''

class AvailableToolView(PyHtmlView):
    TEMPLATE_STR = """
    <div>TOOL:
        <div class="grid-cell">{{ pyview.subject }}</div>
        <div class="grid-cell">Task: {{ pyview.subject.task_definition }}</div>
        <div class="grid-cell">Task name: {{ pyview.subject.task_definition.name }}</div>
        <div class="grid-cell">Task desc: {{ pyview.subject.task_definition.description }}</div>
        <div class="grid-cell">Schema: {{ pyview.subject.task_definition.function_schema }}</div>
        <div class="grid-cell">Need approval: {{ pyview.subject.task_definition.requires_approval }}</div>
        <div class="grid-cell">TaskAgent: {{ pyview.subject.tool_agent_version }}</div>
    </div><br>
    """
    def __init__(self, subject:AgentVersionAvailableTool, parent: PyHtmlView | PyHtmlGuiInstance, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.s = subject


class ToolListView(PyHtmlView):
    TEMPLATE_STR = """
        <b>Available Tools</b><br>
        {{ pyview.agent_task_calls_view.render() }}
    """
    
    def __init__(self, subject:AgentVersion, parent: PyHtmlView | PyHtmlGuiInstance, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.s = subject
        self.agent_task_calls_view = QuerySetView(subject=subject.tools, parent=self, item_class=AvailableToolView)
