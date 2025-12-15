from django.db import models
from core.models.base_model import BaseModel
from django.db.models import Q

class AgentTask(BaseModel):
    class AgentInstanceTaskStatusChoices(models.TextChoices):
        PENDING = 'PENDING', 'PENDING'
        ACTIVE = 'ACTIVE', 'ACTIVE'
        SUCCESS = 'SUCCESS', 'SUCCESS'
        ERROR = 'ERROR', 'ERROR'
        
    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name ='tasks')
    agentInstance = models.ForeignKey("agents.AgentInstance", on_delete=models.CASCADE, related_name ='tasks')
    parent = models.ForeignKey("self", on_delete=models.SET_DEFAULT, related_name ='children', default=None, null=True, blank=True)

    status = models.CharField(max_length=30, choices=AgentInstanceTaskStatusChoices.choices, default=AgentInstanceTaskStatusChoices.PENDING)
    group = models.CharField(max_length=1000, blank=True, default=None, null=True)

    arguments = models.JSONField(default=list)
    result = models.JSONField(default=dict)

    def as_client_dict(self):
        return {}
    
    def check_children_finished(self):
        if self.children.filter(Q(status="PENDING") | Q(status="ACTIVE")).count() > 0:
            return False
        for child in self.children.filter(Q(status="SUCCESS") | Q(status="ERROR")):
            if child.check_children_finished() is False:
                return False
        return True

    def finish(self, status, result):
        from events.event_dispatcher import EventDispatcher
        self.status = status
        self.result = result
        self.save()
        print("MAY BE FINISHED")
        EventDispatcher.event_agenttask_pre_finish(agent=self.agent, agentInstance=self.agentInstance, agentTask=self)

        self.refresh_from_db()
        print("MAY BE FINISHED", self.status)
        if self.status in ["SUCCESS", "ERROR"]:
            
            EventDispatcher.event_agenttask_finished(agent=self.agentInstance.agent, agentInstance=self.agentInstance, agentTask=self)
            if self.parent and self.parent.check_children_finished():
                EventDispatcher.event_agenttask_children_finished(agent= self.parent .agentInstance.agent, agentInstance= self.parent.agentInstance, agentChildTasks=list(self.parent.children.all()))
