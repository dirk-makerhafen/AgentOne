from django.db.models import Q

from agents.models.conversation_message import ConversationMessagePart
from agents.models.llm_query import QueryMessagePart
from core.models.prompt import Prompt
from tools.base.base_tool import BaseTool
from .models.a2a_description import AgentToAgentDescription
from .models.a2a_message import AgentToAgentMessage
from .models.a2a_permission import AgentToAgentPermission
from .prompts import TOOLS, PROMPTS
from .apps import ToolsBuiltinA2aConfig

class A2ATool(BaseTool):
    DESCRIPTION = "Facilitates communication between different agent instances. Allows an agent to send messages to other agents and manage its own public description to inform others of its current status."
    TOOLS = TOOLS
    PROMPTS = PROMPTS


    def get_header_parts(self):
        instructionsTemplate = Prompt.get_template(self.agentInstance, source=ToolsBuiltinA2aConfig.name, key="instructions")
        functionsTemplate = Prompt.get_template(self.agentInstance, source=ToolsBuiltinA2aConfig.name, key="functions")
        return [
            QueryMessagePart(promptVariant=instructionsTemplate, tags=["Prompts", "A2A"]),
            QueryMessagePart(promptVariant=functionsTemplate   , tags=["Prompts", "A2A"])
        ]
        return [
            {"tpId": instructionsTemplate.pk, "tags": ["Prompts", "A2A"], "data":{}},
            {"tpId": functionsTemplate.pk,   "tags": ["Prompts", "A2A"], "data":{}},
        ]
    
    def get_content_parts(self):
        from agents.models.agent_instance import AgentInstance
        from agents.models.agent_instance_fork import AgentInstanceFork
        from agents.models.sub_agent_link import SubAgentLink

        current_instance = self.agentInstance

        # 1. Get explicitly permitted agents
        can_send_to_pks = AgentToAgentPermission.objects.filter(source_instance=current_instance, can_send=True).values_list('target_instance_id', flat=True)
        can_receive_from_pks = AgentToAgentPermission.objects.filter(target_instance=current_instance, can_receive=True).values_list('source_instance_id', flat=True)

        all_communicatable_pks = set(list(can_send_to_pks) + list(can_receive_from_pks))

        # 2. Get implicitly permitted agents (familial and hierarchical)
        # Get sub-agents (children of current instance)
        subordinate_pks = set(SubAgentLink.objects.filter(supervisor_instance=current_instance).values_list('subordinate_instance_id', flat=True))
        all_communicatable_pks.update(subordinate_pks)

        # Get supervisor (parent of current instance)
        supervisor_pk = None
        try:
            supervisor_link = SubAgentLink.objects.get(subordinate_instance=current_instance)
            supervisor_pk = supervisor_link.supervisor_instance.pk
            all_communicatable_pks.add(supervisor_pk)
        except SubAgentLink.DoesNotExist:
            pass

        # Get forked children (children of current instance)
        forked_child_pks = set(AgentInstanceFork.objects.filter(parent_instance=current_instance).values_list('child_instance_id', flat=True))
        all_communicatable_pks.update(forked_child_pks)

        # Get fork parent (parent of current instance)
        fork_parent_pk = None
        try:
            fork_origin = AgentInstanceFork.objects.get(child_instance=current_instance)
            fork_parent_pk = fork_origin.parent_instance.pk
            all_communicatable_pks.add(fork_parent_pk)
        except AgentInstanceFork.DoesNotExist:
            pass

        # Ensure the current instance isn't in the list
        all_communicatable_pks.discard(current_instance.pk)

        if not all_communicatable_pks:
            return []

        instances = AgentInstance.objects.filter(pk__in=all_communicatable_pks).select_related('agent')

        # We can add relationship type to the description for clarity to the LLM
        agents_data = []
        for instance in instances:
            instance_data = {
                "name": instance.name, 
                "agent_id": instance.pk, 
                "description": instance.description_text or instance.agent.description,
                "relationship": "Permitted" # Default relationship
            }

            # Check and assign specific relationship types for better context
            if instance.pk in subordinate_pks:
                instance_data["relationship"] = "Sub-agent"
            elif instance.pk == supervisor_pk:
                 instance_data["relationship"] = "Supervisor"
            elif instance.pk in forked_child_pks:
                instance_data["relationship"] = "Forked Child"
            elif instance.pk == fork_parent_pk:
                instance_data["relationship"] = "Fork Parent"

            agents_data.append(instance_data)

        agents_data.sort(key=lambda x: (x['relationship'], x['name']))

        agentListTemplate = Prompt.get_template(self.agentInstance, source=ToolsBuiltinA2aConfig.name, key="agentlist")
        return [
            QueryMessagePart(
                promptVariant=agentListTemplate, 
                tags=["Prompts", "A2A"], 
                template_data={"agents": agents_data}
            ),
        ]
        #return [
        #    {"tpId": agentListTemplate.pk,   "tags": ["Prompts", "A2A"], "data":{"agents": agents_data}}
        #]

    def agent_send_message(self, toolCall, agent_id: int, message: str):
        from agents.models.agent_instance import AgentInstance
        from agents.models.agent_instance_fork import AgentInstanceFork
        from agents.models.sub_agent_link import SubAgentLink

        sender_instance = toolCall.agentInstance

        try:
            recipient_instance = AgentInstance.objects.get(pk=agent_id)
        except AgentInstance.DoesNotExist:
            return False, {"status": "failed", "error": f"Agent instance with PK {agent_id} not found."}

        # --- IMPLICIT PERMISSION CHECK (Hierarchical & Familial Relationships) ---
        can_communicate_implicitly = False

        # 1. Check for Supervisor-Subordinate relationship
        # Is sender the supervisor of recipient?
        if SubAgentLink.objects.filter(supervisor_instance=sender_instance, subordinate_instance=recipient_instance).exists():
            can_communicate_implicitly = True
        # Is sender the subordinate of recipient (i.e., recipient is supervisor of sender)?
        elif SubAgentLink.objects.filter(supervisor_instance=recipient_instance, subordinate_instance=sender_instance).exists():
            can_communicate_implicitly = True

        # 2. Check for Fork relationship
        # Is sender the parent of recipient?
        elif AgentInstanceFork.objects.filter(parent_instance=sender_instance, child_instance=recipient_instance).exists():
            can_communicate_implicitly = True
        # Is sender the child of recipient (i.e., recipient is parent of sender)?
        elif AgentInstanceFork.objects.filter(parent_instance=recipient_instance, child_instance=sender_instance).exists():
            can_communicate_implicitly = True

        # --- EXPLICIT PERMISSION CHECK (only if no implicit permission found) ---
        if not can_communicate_implicitly:
            can_communicate = AgentToAgentPermission.objects.filter(
                (Q(source_instance=sender_instance, target_instance=recipient_instance, can_send=True)) |
                (Q(source_instance=recipient_instance, target_instance=sender_instance, can_receive=True))
            ).exists()
        else:
            can_communicate = True # Implicit permission granted

        if not can_communicate:
            return False, {"status": "failed", "error": "Permission to send message to this agent instance denied."}

        # 1. Inject the message into the recipient's conversation history
        # This message is what the recipient agent will "see"
        content = f"""Message from {sender_instance.name} (Instance PK: {sender_instance.pk}):\n{message}"""
        recipient_message = recipient_instance.add_to_conversation(role="user", parts=[{"type": ConversationMessagePart.ConversationMessagePartContentType.TEXT, "content": content}])

        # 2. Create the AgentToAgentMessage to log the full transaction
        iam = AgentToAgentMessage()
        iam.sender_agent=sender_instance.agent
        iam.sender_agentInstance=sender_instance
        iam.sender_conversationMessage=toolCall.conversationMessage
        iam.sender_toolCall=toolCall
        iam.receiver_agent=recipient_instance.agent
        iam.receiver_agentInstance=recipient_instance
        iam.receiver_conversationMessage=recipient_message
        iam.message = message
        iam.save()

        # 3. Trigger the recipient agent to process the new message
        recipient_instance.start_or_continue() 

        return True, {"status":"success"}

    def get_history_limiting_rules(self):
        limit = self.agentInstance.effective_limit_max_conversation_messages
        return [
            {
                'group_name': "Agent2Agent",
                'name': 'any',
                'description': 'General limit for all inter-agent communication messages.',
                'match': lambda tc: tc.function_name == 'agent_send_message',
                'key': lambda tc: '',
                'limits': {
                    'pending': limit, 
                    'success': 10, 
                    'failed': 5, 
                    'max': 10
                }
            },{
                'group_name': "Agent2Agent",
                'name': 'recipient',
                'description': 'Limits inter-agent communication history per recipient.',
                'match': lambda tc: tc.function_name == 'agent_send_message',
                'key': lambda tc: tc.arguments.get('recipient_instance_pk'),
                'limits': {
                    'pending': limit, 
                    'success': 5, 
                    'failed': 5, 
                    'max': 8
                }
            },{
                'group_name': "Agent2Agent",
                'name': 'description update',
                'description': 'Limits number of description update toolcalls we see',
                'match': lambda tc: tc.function_name == 'set_agent_description',
                'key': lambda tc: '',
                'limits': {
                    'pending': limit, 
                    'success': 2, 
                    'failed': 2, 
                    'max': 3
                }
            }
        ]

    def set_agent_description(self, toolCall, description: str):
        """
        Sets or updates the public description of the current agent instance.
        This description is visible to other agents and users.
        It should be a concise summary of the agent's current task or status.
        Args:
            toolCall: The ToolCall object initiating the action.
            description (str): A brief summary of the agent's current activity.
                               Max 2-3 sentences, abbreviations/keywords are encouraged.
        """
        if not isinstance(description, str) or len(description) > 512:
             return False, {"status": "failed", "error": "Description must be a string with a maximum length of 512 characters."}

        latest_log = self.agentInstance.description_logs.order_by('-created_at').first()
        if latest_log and latest_log.description == description:
            return True, {}
        AgentToAgentDescription.objects.create(
            agent=self.agentInstance.agent,
            agent_instance=self.agentInstance,
            description=description,
            toolCall=toolCall
        )
        return True, {}
