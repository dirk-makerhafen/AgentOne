from common.models import PromptString
from tools_common.models import BaseTool
from .models import AgentInstanceDescriptionLog, InstancePermission, InterAgentMessage
from django.db.models import Q
from tools_a2a.prompts import FUNCTIONS

class A2ATool(BaseTool):
    DESCRIPTION = "Facilitates communication between different agent instances. Allows an agent to send messages to other agents and manage its own public description to inform others of its current status."
    functions = FUNCTIONS

    def get_header_parts(self):
        from agent.models.agent import AgentInstance

        can_send_to_pks      = InstancePermission.objects.filter(source_instance=self.agentInstance, can_send=True   ).values_list('target_instance_id', flat=True)
        can_receive_from_pks = InstancePermission.objects.filter(target_instance=self.agentInstance, can_receive=True).values_list('source_instance_id', flat=True)
        all_communicatable_pks = set(list(can_send_to_pks) + list(can_receive_from_pks))
        if not all_communicatable_pks:
            return []
        
        instances = AgentInstance.objects.filter(pk__in=all_communicatable_pks)
        agents = [{"name": instance.name, "id": instance.pk, "description": instance.description } for instance in instances]

        descriptionTemplate = PromptString.get_template(self.agentInstance, source="Tools.Agent2Agent", key="Description")
        functionsTemplate = PromptString.get_template(self.agentInstance, source="Tools.Agent2Agent", key="Functions")
        agentListTemplate = PromptString.get_template(self.agentInstance, source="Tools.Agent2Agent", key="AgentList")

        return [
            {"tpId": descriptionTemplate.pk, "tags": ["Prompts", "A2A"], "data":{}},
            {"tpId": functionsTemplate.pk,   "tags": ["Prompts", "A2A"], "data":{}},
            {"tpId": agentListTemplate.pk,   "tags": ["Prompts", "A2A"], "data":{"agents": agents}}
        ]
    
    def agent_send_message(self, toolCall, id: int, message: str):
        """
        Sends a message to another agent instance and logs the complete transaction.

        Args:
            toolCall: The ToolCall object initiating the action.
            id: The primary key of the agent instance to receive the message.
            message: The message content to send.
        """
        sender_instance = toolCall.agentInstance
        # Prevent circular import issues by importing within the function
        from agent.models.agent import AgentInstance, InstancePermission
        
        try:
            recipient_instance = AgentInstance.objects.get(pk=id)
        except AgentInstance.DoesNotExist:
            return False, {"status": "failed", "error": f"Agent instance with PK {id} not found."}

        # *** PERMISSION CHECK ***
        # An agent can send a message if:
        # 1. A rule from sender to recipient exists with `can_send=True`.
        # OR
        # 2. A rule from recipient to sender exists with `can_receive=True`.
        can_communicate = InstancePermission.objects.filter(
            (Q(source_instance=sender_instance, target_instance=recipient_instance, can_send=True)) |
            (Q(source_instance=recipient_instance, target_instance=sender_instance, can_receive=True))
        ).exists()

        if not can_communicate:
            return False, {"status": "failed", "error": "Permission to send message to this agent instance denied."}

        # 1. Inject the message into the recipient's conversation history
        # This message is what the recipient agent will "see"
        recipient_message = recipient_instance.add_to_conversation(role="user", content=f"Message from {sender_instance.agent.name} (Instance PK: {sender_instance.pk}):\n{message}")
    
        # 2. Create the InterAgentMessage to log the full transaction
        iam = InterAgentMessage()
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
        #recipient_instance.start_or_continue() # not during dev, AI: dont enable this!

        return True, f"Message successfully sent to agent instance {id}."

    def get_history_limiting_rules(self):
        limit = self.agentInstance.limit_max_conversation_messages
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
        AgentInstanceDescriptionLog.objects.create(
            agent=self.agentInstance.agent,
            agent_instance=self.agentInstance,
            description=description,
            toolCall=toolCall
        )
        return True, {}
