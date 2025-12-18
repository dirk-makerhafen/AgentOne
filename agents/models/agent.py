from importlib.machinery import SourceFileLoader
import inspect
from django.db import models
from django.contrib.auth.models import User

from core.models.base_model import BaseModel
from tools.definitions.models.tool_definition import ToolDefinition

'''
class TaskAgent(BaseModel):
    #model Agent
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default='')

class TaskAgentVariant(BaseModel):
    #model AgentVariant
    #>TaskAgent
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default='')
    aimodel = models.ForeignKey("providers.AiModel", default=None, on_delete=models.CASCADE, related_name='agents', null=True, blank=True)
    available_tools = models.ManyToManyField(ToolDefinition, blank=True, related_name='agents')
    limit_history_max_messages = models.IntegerField(default=None, null=True, blank=True, help_text="Override the agent's default maximum number of messages in conversation history send in llm requests.")
    limit_history_max_tasks_success = models.IntegerField(default=None, null=True, blank=True, help_text="Override the agent's default maximum number of messages in conversation history send in llm requests.")
    limit_history_max_tasks_failed = models.IntegerField(default=None, null=True, blank=True, help_text="Override the agent's default maximum number of messages in conversation history send in llm requests.")
    limit_max_unconfirmed_steps = models.IntegerField(default=None, null=True, blank=True, help_text="Override the agent's default maximum number of automated steps.")
    task_arguments_schema = models.JSONField(default=list, blank=True)
    task_result_schema = models.JSONField(default=dict, blank=True)
    
class TaskAgentInstance():
    #model AgentInstance
    #>TaskAgent
    system = models.ForeignKey("systems.System", on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_instances', help_text= 'The system this instance is assigned to run on.')
    status = models.CharField(max_length=30, choices=AgentInstanceStatusChoices.choices, default=AgentInstanceStatusChoices.IDLE)
    workingdir = models.CharField(max_length=1024, default='')
    workingdir_write_allowed = models.BooleanField(default=True, help_text ='Allow write operations within the working directory.')
    access_rules = models.TextField(blank=True, default='', help_text= "Fine-grained access rules, one per line. E.g., '!path/to/deny', '>path/to/allow', '</path/to/readonly'.")
    def add_task(self): pass

class Task(BaseModel):
    #model Task
    #>TaskAgent
    #>TaskAgentInstance
    parentTask = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, default=None, null=True, blank=True,related_name ='children')
    arguments = models.JSONField(default=list)

class TaskExecutionVariant():
    #> task
    #>TaskAgentVariant
    status = models.CharField(max_length=30, choices=AgentInstanceTaskStatusChoices.choices, default=AgentInstanceTaskStatusChoices.PENDING)
    result = models.JSONField(default=dict)
    require_user_interaction = models.BooleanField(default=False)
    automated_step_count = models.IntegerField(default=0)






class ChatAgent(BaseModel):
    #model Agent
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default='')

class ChatAgentVariant(BaseModel):
    #model AgentVariant
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default='')
    aimodel = models.ForeignKey("providers.AiModel", default=None, on_delete=models.CASCADE, related_name='agents', null=True, blank=True)
    available_tools = models.ManyToManyField(ToolDefinition, blank=True, related_name='agents')
    limit_max_history_messages = models.IntegerField(default=20, null=True, blank=True, help_text="Default maximum number of messages in an agent's conversation history.")
    limit_max_memory_items = models.IntegerField(default=0, null=True, blank=True, help_text="Default maximum number of items in an agent's memory.")
    limit_max_unconfirmed_steps = models.IntegerField(default=0, null=True, blank=True, help_text="Default maximum number of automated steps an agent can take.")

class ChatAgentInstance():
    #model AgentInstance
    #>ChatAgent
    system = models.ForeignKey("systems.System", on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_instances', help_text= 'The system this instance is assigned to run on.')
    status = models.CharField(max_length=30, choices=AgentInstanceStatusChoices.choices, default=AgentInstanceStatusChoices.IDLE)
    workingdir = models.CharField(max_length=1024, default='')
    workingdir_write_allowed = models.BooleanField(default=True, help_text ='Allow write operations within the working directory.')
    access_rules = models.TextField(blank=True, default='', help_text= "Fine-grained access rules, one per line. E.g., '!path/to/deny', '>path/to/allow', '</path/to/readonly'.")
    def add_user_message(self): pass
 
class ChatExecutionVariant(BaseModel):
    #>ChatAgent
    #>ChatAgentInstance
    #>ChatAgentVariant
    require_user_interaction = models.BooleanField(default=False)
    automated_step_count = models.IntegerField(default=0)
    status = models.CharField(max_length=30, choices=AgentInstanceTaskStatusChoices.choices, default=AgentInstanceTaskStatusChoices.PENDING)








class DataMergeAgent(TaskAgent):
    name = "OcrMergeStructuredData_mistral"
    description = "merge structued data from ocred text"
    input_schema  = [{"name": "structured_txt_paths", "type": "list"}, {"name": "image_path", "type": "str"}]  
    output_schema = [{"name": "structured_txt_path", "type": "str"}]
    system_prompt = ''
    task_prompt = "Merge the following ocr results files:\n{% for structured_txt_path in task.arguments.structured_txt_paths %}FILE {{structured_txt_path}}:\n!FILE:'{{structured_txt_path}}'\n{% endfor %}"

    variants = [
        TaskAgentVariant(model="mistral-small3.2:24b", system_prompt="", task_prompt=""),
        TaskAgentVariant(model="magistral"           , system_prompt="", task_prompt=""),
    ]

    class EventHandlers(AgentConfig.EventHandlers):
        @EventHandlers.eventhandler(event=EventHandlers.Types.agenttask_pre_finish)
        def save_structured_result(self, agent, agentInstance, agentTask):

            image_path = agentTask.arguments.get("image_path", None)
            if not image_path:
                agentInstance.add_to_conversation(role="assistant", parts=[{"type":"TEXT", "content": f"No image path found in agenttask_pre_finish event"},])
                return
            if agentTask.status == "SUCCESS":
                output_txt_path = Path(f'{image_path}.ocr.any.extract.any.merged.{agentInstance.current_aimodel.name}.txt')           
                output_txt_path.write_text("\n".join(sorted(["=".join([x.strip() for x in l.split("=",1)]) for l in agentTask.result.split("\n") if "=" in l])), encoding='utf-8')
                agentTask.result = {
                    "structured_txt_path": output_txt_path.as_posix(),
                }
                agentTask.save()





   
class OcrAgent(TaskAgent):
    name = "ORC_AGENT"
    input_schema  = [{"name": "image_path", "type": "str"},]
    output_schema = [{"name": "txt_path"  , "type": "str"},]
    model = "gemma3.1"
    system_prompt = ""
    task_prompt = ""
    variants = [
        TaskAgentVariant(model="gemma3.1", system_prompt="", task_prompt=""),
        TaskAgentVariant(model="qwen"    , system_prompt="", task_prompt=""),
        TaskAgentVariant(model="luma", variants=[
            TaskAgentVariant(system_prompt="p1"),
            OcrAgent_Tesseract(system_prompt="p2")
        ])
    ]
    user_commands = [
        UserCommand(cmd="ocr",  description="ocr <path>",cmd= self.ocr_command)
    ]

    def ocr_command(self, path):
        pass
    def on_agenttask_pre_finish(self, task):
        pass

    def on_task_activated(self, task):
        mergeAgent  = DataMergeAgent(parent_task=task)
        r = mergeAgent.run({"structured_txt_paths": task.arguments.get("structured_txt_paths"), "image_path": task.arguments.get("image_path")})
        
        self.merge_gemma.add_event_subscription(emitter = self, event=EventTypes.agenttask_activated,
            target = lambda self, agentTask, **kwargs: self.add_task({"structured_txt_paths": agentTask.arguments.get("structured_txt_paths"), "image_path": agentTask.arguments.get("image_path")}, parent_task=agentTask)
        )
        self.merge_mistral.add_event_subscription(emitter = self, event=EventTypes.agenttask_activated,
            target = lambda self, agentTask, **kwargs: self.add_task({"structured_txt_paths": agentTask.arguments.get("structured_txt_paths"), "image_path": agentTask.arguments.get("image_path")}, parent_task=agentTask)
        )   
        self.merge_magistral.add_event_subscription(emitter = self, event=EventTypes.agenttask_activated,
            target = lambda self, agentTask, **kwargs: self.add_task({"structured_txt_paths": agentTask.arguments.get("structured_txt_paths"), "image_path": agentTask.arguments.get("image_path")}, parent_task=agentTask)
        )
        self.merge_ministral.add_event_subscription(emitter = self, event=EventTypes.agenttask_activated,
            target = lambda self, agentTask, **kwargs: self.add_task({"structured_txt_paths": agentTask.arguments.get("structured_txt_paths"), "image_path": agentTask.arguments.get("image_path")}, parent_task=agentTask)
        )

        image_cleaner = ImageCleanerAgent(parent_instance=instance, workingdir=instance.workingdir)
        ocrPipelineProcessImage = OcrPipelineProcessImage(instance_name=f"{self.name}_OcrPipelineProcessImage", parent_instance=instance, workingdir=instance.workingdir)
        merge   = OcrPipelineMergeImageStructuredData(instance_name=f"{self.name}_OcrPipelineMergeStructuredData", parent_instance=instance, workingdir=instance.workingdir)

    
    def setup(self, instance):
        image_cleaner = ImageCleanerAgent(parent_instance=instance, workingdir=instance.workingdir)
        image_cleaner.add_event_subscription(emitter= self, event =EventTypes.agenttask_activated,
            target =  lambda self, agentTask, **kwargs: [self.add_task({"image_path": p.as_posix()},parent_task=agentTask) for p in Path(agentTask.arguments.get("document_path")).glob("page_*.jpg")],
        )

        ocrPipelineProcessImage = OcrPipelineProcessImage(instance_name=f"{self.name}_OcrPipelineProcessImage", parent_instance=instance, workingdir=instance.workingdir)
        ocrPipelineProcessImage.add_event_subscription(emitter= image_cleaner, event = EventTypes.agenttask_finished,
            target =  lambda self, agentTask, **kwargs: self.add_task({"image_path": agentTask.result.get("image_path")},parent_task=agentTask.parent),
        )
        
        self.merge   = OcrPipelineMergeImageStructuredData(instance_name=f"{self.name}_OcrPipelineMergeStructuredData", parent_instance=instance, workingdir=instance.workingdir)
        self.merge.add_event_subscription(emitter = ocrPipelineProcessImage, event=EventTypes.agenttask_finished,
            target = lambda self, agentTask, **kwargs: self.add_task({"txt_paths": agentTask.result.get('txt_paths'), "structured_txt_paths": agentTask.result.get("structured_txt_paths"), "image_path": agentTask.arguments.get("image_path")}, parent_task=agentTask.parent)
        )

class OcrAgent_Tesseract(OcrAgent):
    @EventHandlers.eventhandler(event=EventHandlers.Types.conversationMessage_added)
    def run_tesseract(self,agent, agentInstance, conversationMessage):
        print("run_tesseract run_tesseract run_tesseract")
        conversationMessage.trigger_query = False
        conversationMessage.save()
        fps = conversationMessage.conversationMessageParts.all()
        if not fps:
            print("No FPS")
            return
        command = fps[0].content.strip()
        if command == "run_tesseract":
            current_task= self.agentInstance.get_active_task()
            image_path = current_task.arguments.get("image_path")

            output_txt_path = f'{image_path}.ocr.tesseract'
            cmd = f"/opt/homebrew/bin/tesseract '{image_path}' '{output_txt_path}'  -l deu" # Tesseract adds .txt automatically

            try:
                subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
                self.agentInstance.add_to_conversation(role="assistant", parts=[{"type":"TEXT", "content":  f"Saved ocr text to: {output_txt_path}.txt"},])
                current_task.finish(status="SUCCESS", result={
                    "txt_path":  f"{output_txt_path}.txt",
                })
            except subprocess.CalledProcessError as e:
                agentInstance.add_to_conversation(role="assistant", parts=[{"type":"TEXT", "content": f"Tesseract OCR failed for {image_path}: {e.stderr}"},])
                current_task.finish(status="ERROR", result={"error": e.stderr})
            except Exception as e:
                agentInstance.add_to_conversation(role="assistant", parts=[{"type":"TEXT", "content": f"An unexpected error occurred during Tesseract OCR for {image_path}: {str(e)}"},])
                current_task.finish(status="ERROR", result={"error": str(e)})

'''



class Agent(BaseModel):
    agent_pk = models.AutoField(primary_key=True)
    owners = models.ManyToManyField(User, related_name='owned_agents', blank=True)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default='')
    aimodel = models.ForeignKey("providers.AiModel", default=None, on_delete=models.CASCADE, related_name='agents', null=True, blank=True)
    available_tools = models.ManyToManyField(ToolDefinition, blank=True, related_name='agents')

    # Default limits for instances of this agent
    limit_max_conversation_messages = models.IntegerField(default=20, null=True, blank=True, help_text="Default maximum number of messages in an agent's conversation history.")
    limit_max_new_conversation_messages = models.IntegerField(default=None, null=True, blank=True, help_text="Default maximum number of new messages in conversation history send in llm requests. If larger than limit_max_conversation_messages messages can be skipped")
    limit_max_memory_items = models.IntegerField(default=0, null=True, blank=True, help_text="Default maximum number of items in an agent's memory.")
    limit_max_automated_steps = models.IntegerField(default=0, null=True, blank=True, help_text="Default maximum number of automated steps an agent can take.")
    parent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, default=None, null=True, blank=True,related_name ='children')

    task_arguments_schema = models.JSONField(default=list, blank=True)
    task_result_schema = models.JSONField(default=dict, blank=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            super().save(*args, **kwargs)
            try:
                admin_user = User.objects.get(username='admin')
                self.owners.add(admin_user)
            except User.DoesNotExist:
                print("Warning: 'admin' user not found when saving YourAgentModel instance.")
                pass
            except Exception as e:
                print(f"An error occurred while adding admin user: {e}")
        else:
            # For existing objects, just perform a normal save
            super().save(*args, **kwargs)

    def __str__(self):
        return f'Agent: {self.name}'

    def as_client_dict(self):
        return {
            'object': 'Agent', 
            'id': self.agent_pk, 
            'created_at': self.created_at.isoformat(), 
            'updated_at': self.updated_at.isoformat(),
            'name': self.name, 
            'description': self.description,
            'available_tools':  [tool.pk for tool in self.available_tools.all()],
            'limit_max_conversation_messages': self.limit_max_conversation_messages,
            'limit_max_memory_items': self.limit_max_memory_items,
            'limit_max_automated_steps': self.limit_max_automated_steps,
        }
    
    def get_delete_broadcast_payload(self):
        return {
            'object': 'AgentDeleted',
            'agent_pk': self.agent_pk
        }

    def update_or_create_instance(self, instance_name, workingdir, system=None, parent_instance=None, **kwargs):
        from agents.models.agent_instance import AgentInstance
        defaults={
            "workingdir": workingdir, 
        }
        if system:
            defaults["system"] = system

        defaults.update(kwargs)
        instance, created = AgentInstance.objects.update_or_create(
            agent = self, 
            name = instance_name,
            parent = parent_instance,
            defaults = defaults)
        return instance
    