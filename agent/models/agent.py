from django.db import models
from agent.models.conversation import ConversationMessage
from common.models import ModelWithJsonData
from tools_filesystem.filesystem import FilesystemTool
from tools_memory.memory import SMLMemoryTool
from tools_python.pythontool import PythonTool
from tools_a2a.tool import A2ATool
from tools_userinteraction.tool import UserInteractionTool
from tools_shell.shelltool import ShellTool
from tools_subscriptions.tool import SubscriptionsTool
from tools_a2a.models import AgentInstanceDescriptionLog
import os
from django.db.models import Q, Sum
from providers.models import Model
from django.contrib.auth.models import User
from systems.models import System


class Agent(ModelWithJsonData):
    agent_pk = models.AutoField(primary_key=True)
    owners = models.ManyToManyField(User, related_name='owned_agents', blank=True)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default='')
    model = models.ForeignKey(Model, default=None, on_delete=models.CASCADE, related_name='agents', null=True)

    def __str__(self):
        return f'Agent: {self.name}'

    def save(self, send_to_client=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if send_to_client:
            from dashboard.tasks import send_object_to_clients
            send_object_to_clients(self)

    def as_client_dict(self):
        return {
            'object': 'Agent', 
            'id': self.agent_pk, 
            'created_at': self.created_at.isoformat(), 
            'name': self.name, 
            'description': self.description
        }

class AgentInstance(ModelWithJsonData):
    instance_pk = models.AutoField(primary_key=True)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name ='instances')
    system = models.ForeignKey(System, on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_instances', help_text= 'The system this instance is assigned to run on.')
    model = models.ForeignKey(Model, default=None, null=True, on_delete= models.CASCADE, related_name='agent_instances')
    name = models.CharField(max_length=255, default='', blank=True)
    STATUS_CHOICES = [('IDLE', 'Idle'), ('IDLE_AUTOMATED',
        'Idle (Automated)'), ('THINKING', 'Thinking'), ('EXECUTING_TOOLS',
        'Executing Tools'), ('AWAITING_USER_INPUT', 'Awaiting User Input'),
        ('AWAITING_AGENT_MESSAGE', 'Awaiting Agent Message'), ('FINISHED',
        'Finished'), ('ERROR', 'Error'), ('MISCONFIGURED', 'Misconfigured'),
        ('SYSTEM_OFFLINE', 'System Offline')]
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='IDLE')
    workingdir = models.CharField(max_length=1024, default='')
    require_user_interaction = models.BooleanField(default=False)
    limit_max_conversation_messages = models.IntegerField(default=20)
    limit_max_memory_items = models.IntegerField(default=15)
    limit_max_automated_steps = models.IntegerField(default=0)
    automated_step_count = models.IntegerField(default=0)
    workingdir_write_allowed = models.BooleanField(default=False, help_text ='Allow write operations within the working directory.')
    access_rules = models.TextField(blank=True, default='', help_text= "Fine-grained access rules, one per line. E.g., '!path/to/deny', '>path/to/allow', '</path/to/readonly'.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filesystemTool = FilesystemTool(self)
        self.available_tools = [FilesystemTool, A2ATool, UserInteractionTool, PythonTool, ShellTool, SubscriptionsTool, SMLMemoryTool]
        self.toolname_to_class = {}
        for available_tool in self.available_tools:
            for fname in available_tool.functions.keys():
                self.toolname_to_class[f"{fname}"] = available_tool

    @property
    def description(self):
        latest_log = self.description_logs.order_by('-created_at').first()
        return latest_log.description if latest_log else ''
    
    @description.setter
    def description(self, description, toolCall=None):
        from dashboard.tasks import send_object_to_clients
        d = AgentInstanceDescriptionLog(
            agent=self.agent,
            agent_instance=self,
            description=description,
            toolCall=toolCall
        )
        d.save()
        send_object_to_clients(self)

    def get_tool_function(self, function_name):
        toolInstance = self.toolname_to_class[function_name](self)
        return {
            "arguments": toolInstance.functions[function_name]["parameters"],
            "callable": getattr(toolInstance, function_name)
        } 

    def save(self, send_to_client=True, *args, **kwargs):
        from dashboard.tasks import send_object_to_clients
        is_new = self.pk is None
        old_status = None
        if not is_new:
            old_status = AgentInstance.objects.get(pk=self.pk).status
        super().save(*args, **kwargs)
        if send_to_client:
            send_object_to_clients(self)

    def as_client_dict(self):
        model = self.model or self.agent.model
        model_name = model.name if model else 'N/A'
        model_id = model.pk if model else None
        all_rule_templates = []
        for tool_class in self.available_tools:
            tool_instance = tool_class(self)
            if hasattr(tool_instance, 'get_history_limiting_rules'):
                all_rule_templates.extend(tool_instance.get_history_limiting_rules())
        db_rules = self.history_limiting_rules.filter(is_active=True)
        db_rules_map = {f'{rule.group_name}:{rule.rule_name}': rule for
            rule in db_rules}
        merged_rules = []
        for template in all_rule_templates:
            group_name = template.get('group_name', 'default')
            rule_name = template['name']
            rule_key = f'{group_name}:{rule_name}'
            rule_data = {'group_name': group_name, 'full_rule_name':
                rule_key, 'display_name': rule_name, 'description':
                template.get('description', ''), 'success': template[
                'limits'].get('success'), 'failed': template['limits'].get(
                'failed'), 'pending': template['limits'].get('pending'),
                'max': template['limits'].get('max'), 'db_id': None}
            if rule_key in db_rules_map:
                db_rule = db_rules_map[rule_key]
                rule_data['db_id'] = db_rule.pk
                if db_rule.limit_success is not None:
                    rule_data['success'] = db_rule.limit_success
                if db_rule.limit_failed is not None:
                    rule_data['failed'] = db_rule.limit_failed
                if db_rule.limit_pending is not None:
                    rule_data['pending'] = db_rule.limit_pending
                if db_rule.limit_max is not None:
                    rule_data['max'] = db_rule.limit_max
            merged_rules.append(rule_data)
        grouped_rules = {}
        for rule_item in merged_rules:
            group_name = rule_item.pop('group_name', 'default')
            if group_name not in grouped_rules:
                grouped_rules[group_name] = []
            grouped_rules[group_name].append(rule_item)
        for group_name in grouped_rules:
            grouped_rules[group_name].sort(key=lambda x: x['display_name'])
        token_totals = self.llmResponses.aggregate(total_prompt_tokens=Sum('prompt_tokens'), total_completion_tokens=Sum('completion_tokens'))
        total_prompt = token_totals.get('total_prompt_tokens') or 0
        total_completion = token_totals.get('total_completion_tokens') or 0
        return {
            'object': 'AgentInstance', 
            'id': self.instance_pk,
            'agent_id': self.agent.agent_pk, 
            'created_at': self.created_at.isoformat(), 
            'name': self.name, 
            'description': self.description,
            'status': self.status, 
            'status_display': self.get_status_display(), 
            'agent_name': self.agent.name,
            'agent_description': self.agent.description, 
            'model_name': model_name, 
            'model_id': model_id, 
            'system_name': self.system.name if self.system else 'Unassigned', 
            'system_id': self.system.pk if self.system else None, 
            'workingdir': self.workingdir,
            'limit_max_conversation_messages': self.limit_max_conversation_messages, 
            'limit_max_memory_items': self.limit_max_memory_items, 
            'limit_max_automated_steps': self.limit_max_automated_steps, 
            'automated_step_count': self.automated_step_count, 
            'workingdir_write_allowed': self.workingdir_write_allowed, 
            'access_rules': self.access_rules,
            'history_limiting_rules': grouped_rules, 
            'total_prompt_tokens': total_prompt, 
            'total_completion_tokens': total_completion}

    def __str__(self):
        return f'Instance {self.instance_pk} of Agent {self.agent.name}'

    def clone(self):
        newInstance = AgentInstance()
        newInstance.agent = self.agent
        newInstance.model = self.model
        newInstance.name = f'Cloned {self.name}'
        newInstance.status = self.status
        newInstance.workingdir = self.workingdir
        newInstance.save()
        if self.description:
            AgentInstanceDescriptionLog.objects.create(agent_instance=newInstance, description=self.description)
        paths = set()
        for ctxitem in self.filesystemTool.get_loaded_items():
            paths.add(ctxitem.path)
        for path in paths:
            if os.path.isdir(path):
                newInstance.filesystemTool.directories.load(path=path)
            else:
                newInstance.filesystemTool.load(path=path)
        for message in self.get_conversation_messages(30):
            if message['role'] in ['assistant', 'user'
                ] and 'content' in message:
                newInstance.add_to_conversation(role=message['role'],
                    content=message['content'])
        return newInstance

    def add_to_conversation(self, role, content):
        c = ConversationMessage()
        c.agent = self.agent
        c.agentInstance = self
        c.role = role
        c.data = {'parts': [{'content': content}]}
        c.save()
        return c

    def start_or_continue(self):
        from agent.tasks import celery_create_query
        if self.status in ['THINKING', 'EXECUTING_TOOLS']:
            return
        self.status = 'THINKING'
        self.require_user_interaction = False
        self.save()
        if self.system and self.system.status != 'online':
            print(f"AgentInstance {self.instance_pk} is assigned to system '{self.system.name}' which is not online. Cannot start.")
            self.status = 'SYSTEM_OFFLINE'
            self.save()
            return
        celery_create_query.apply_async(args=[self.instance_pk])
