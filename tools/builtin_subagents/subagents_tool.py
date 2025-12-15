from agents.models.debug_log_entry import DebugLogEntry
from agents.models.llm_query import QueryMessagePart
from tools.base.base_tool import BaseTool
from tools.builtin_filesystem.utils.fsutils import get_abs_path
from .prompts import TOOLS, PROMPTS, REGISTRATION_INSTRUCTION_TEMPLATE
from .apps import ToolsBuiltinSubagentsConfig
from core.models.prompt import Prompt
import traceback
import json
from datetime import datetime
from tools.builtin_a2a.a2a_tool import A2ATool
from django.db.models import Q

class SubAgentTool(BaseTool):
    DESCRIPTION = "Create and manage sub-agents to delegate tasks. Sub-agents run independently and can be communicated with via the a2a_tool."
    TOOLS = TOOLS
    PROMPTS = PROMPTS

    def get_header_parts(self):
        #instructionsTemplate = Prompt.get_template(agentInstance=self.agentInstance, source=ToolsBuiltinSubagentsConfig.name, key="instructions")
        functionsTemplate = Prompt.get_template(agentInstance=self.agentInstance, source=ToolsBuiltinSubagentsConfig.name, key="functions")
        return [
        #    QueryMessagePart(promptVariant=instructionsTemplate, tags=["Prompts", "SubAgents"]),
            QueryMessagePart(promptVariant=functionsTemplate   , tags=["Prompts", "SubAgents"])
        ]

    def get_content_parts(self):
        from agents.models.agent import Agent
        from agents.models.sub_agent_link import SubAgentLink
        parts = []
        user = None
        if self.agentInstance.agent.owners.exists():
            user = self.agentInstance.agent.owners.first()

        # 1. Inject available Agent templates
        if user:
            available_agents_prompt_template = Prompt.get_template(agentInstance=self.agentInstance, source=ToolsBuiltinSubagentsConfig.name, key="available_agents_content")
            available_agents = Agent.objects.filter(owners=user).order_by('name')
            agents_data = [{'pk': agent.pk, 'name': agent.name, 'description': agent.description} for agent in available_agents]
            if agents_data:
                parts.append(QueryMessagePart(
                    promptVariant=available_agents_prompt_template   , 
                    tags=['Tool', 'SubAgentTool', 'AvailableAgents'], 
                    template_data={'available_agents': agents_data})
                )

        # 2. Inject current sub-agents
        current_subagents_prompt_template = Prompt.get_template(agentInstance=self.agentInstance, source=ToolsBuiltinSubagentsConfig.name, key="current_subagents_content")
        sub_agent_links = SubAgentLink.objects.filter(supervisor_instance=self.agentInstance).order_by('created_at')
        subagents_data = [{
            'pk': link.subordinate_instance.pk, 'name': link.subordinate_instance.name, 'status': link.subordinate_instance.status,
            'description': link.subordinate_instance.description_text,
        } for link in sub_agent_links]
        if subagents_data:
            parts.append(QueryMessagePart(
                promptVariant=current_subagents_prompt_template, 
                tags=['Tool', 'SubAgentTool', 'CurrentSubagents'], 
                template_data={'subagents': subagents_data})
            )


        # 3. Inject supervisor agent info
        try:
            supervisor_link = SubAgentLink.objects.get(subordinate_instance=self.agentInstance)
            supervisor_instance = supervisor_link.supervisor_instance
            supervisor_info_prompt_template = Prompt.get_template(agentInstance=self.agentInstance, source=ToolsBuiltinSubagentsConfig.name, key="supervisor_info_content")
            supervisor_data = {
                'pk': supervisor_info_prompt_template.subordinate_instance.pk, 'name': supervisor_info_prompt_template.subordinate_instance.name, 'status': supervisor_info_prompt_template.subordinate_instance.status,
                'description': supervisor_info_prompt_template.subordinate_instance.description_text,
            }
            parts.append(QueryMessagePart(
                promptVariant=current_subagents_prompt_template, 
                tags=['Tool', 'SubAgentTool', 'SupervisorInfo'], 
                template_data={'supervisor': supervisor_data})
            )

        except SubAgentLink.DoesNotExist:
            pass
        except Exception as e:
            print(f"Error injecting supervisor info: {e}")

        return parts

    def update_working_dir(self, agent_id, workingdir, toolCall=None):
        from agents.models.agent_instance import AgentInstance
        agentInstance = AgentInstance.objects.get(pk=agent_id)
        agentInstance.set_workingdir(workingdir=workingdir)
        return True, {}

    def create(self, agent_name: str, agent_description: str, based_on_agent_pk: int = None, workingdir: str = None, toolCall=None):
        from agents.models.agent import Agent
        from agents.models.agent_instance import AgentInstance
        from agents.models.sub_agent_link import SubAgentLink
        from django.contrib.auth.models import User
        from core.logging import log_to_clients

        try:
            supervisor_instance = self.agentInstance
            user = User.objects.get(pk=self.agentInstance.agent.owners.first().pk)

            if based_on_agent_pk:
                try:
                    base_agent = Agent.objects.get(pk=based_on_agent_pk, owners=user)
                except Agent.DoesNotExist:
                    log_to_clients(f"Error: Base agent with pk {based_on_agent_pk} not found or permission denied.", level='error', users=[user])
                    return (False, {"status": "error", "message": f"Base agent with pk {based_on_agent_pk} not found or permission denied."})
            else:
                base_agent, created = Agent.objects.get_or_create(
                    name="Default SubAgent Template",
                    defaults={'description': "A default template for creating sub-agents."}
                )
                if created:
                    base_agent.owners.add(user)
                    base_agent.save()
                    log_to_clients(f"Created default sub-agent template: '{base_agent.name}'", level='info', users=[user])

            sub_agent_workingdir = get_abs_path(supervisor_instance.workingdir, workingdir) if workingdir is not None else supervisor_instance.workingdir

            sub_agent_instance = AgentInstance.objects.create(
                agent=base_agent, name=agent_name, description_text=agent_description, workingdir=sub_agent_workingdir,
                workingdir_write_allowed=supervisor_instance.workingdir_write_allowed, access_rules=supervisor_instance.access_rules,
                system=supervisor_instance.system, aimodel=supervisor_instance.current_aimodel
            )

            SubAgentLink.objects.create(supervisor_instance=supervisor_instance, subordinate_instance=sub_agent_instance)

            agent_info = {
                "name": sub_agent_instance.name, "purpose": agent_description,
                "working_directory": sub_agent_workingdir, "id": sub_agent_instance.pk
            }
            kv_registration_value = json.dumps(agent_info)
            kv_registration_key = f"team:agents:{sub_agent_instance.pk}:info"

            registration_instruction = REGISTRATION_INSTRUCTION_TEMPLATE.format(
                supervisor_id=supervisor_instance.pk,
                key=kv_registration_key,
                value=kv_registration_value
            )
            
            a2a_tool_instance = A2ATool(self.agentInstance)
            success_send_msg, result_send_msg = a2a_tool_instance.agent_send_message(
                toolCall=toolCall, agent_id=sub_agent_instance.pk, message=registration_instruction
            )

            if success_send_msg:
                log_to_clients(f"Sub-agent '{agent_name}' (ID: {sub_agent_instance.pk}) created and instructed to register itself in KV store.", level='info', users=[user])
            else:
                log_to_clients(f"Sub-agent '{agent_name}' (ID: {sub_agent_instance.pk}) created, but failed to send KV registration instruction: {result_send_msg.get('message', 'Unknown error')}", level='warning', users=[user])
            
            from events.event_dispatcher import EventDispatcher
            EventDispatcher.event_agentinstance_created(base_agent, sub_agent_instance)
            return (True, {
                "status": "success", "sub_agent_instance_id": sub_agent_instance.pk, "sub_agent_instance_name": sub_agent_instance.name,
                "message": f"Sub-agent '{agent_name}' created and linked successfully. KV registration instruction sent."
            })
        except User.DoesNotExist:
            return (False, {"status": "error", "message": "Supervisor agent has no associated user owner. Cannot create sub-agent."})
        except Exception as e:
            error_message = f"Error creating sub-agent: {e} {traceback.format_exc()}"
            user_to_log = [user] if 'user' in locals() else []
            log_to_clients(error_message, level='error', users=user_to_log)
            return (False, {"status": "error", "message": error_message})