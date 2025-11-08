import json
from channels.generic.websocket import WebsocketConsumer
from asgiref.sync import async_to_sync
from ui.router import MESSAGE_HANDLERS
import traceback

# Import all consumer modules to ensure their @register_handler decorators run
from agents.consumers import agent, agent_instance, conversation, limits
from core.consumers import prompts
from providers.consumers import api_key, api_provider, ai_model
from systems.consumers import system
from tools.builtin_a2a.consumers import permissions
from tools.builtin_filesystem.consumers import filesystem
from tools.builtin_memory.consumers import memory
from tools.calls.consumers import direct_tool_call
from tools.definitions.consumers import tool_definition, tool_installation
from tools.instances.consumers import tool_instance


class UiConsumer(WebsocketConsumer):
    def connect(self):
        self.user_pk = self.scope['url_route']['kwargs'].get('user_pk')
        if not self.user_pk:
            self.close()
            return
        
        self.group_name = f'user_{self.user_pk}'
        async_to_sync(self.channel_layer.group_add)(self.group_name, self.channel_name)
        self.accept()

    def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            async_to_sync(self.channel_layer.group_discard)(self.group_name, self.channel_name)

    def receive(self, text_data):
        try:
            data = json.loads(text_data)
            print("websocket received:", data)
            message_type = data.get('type')
            payload = data.get('payload', {})

            # Special handling for agent instance subscriptions, which is a consumer-level concern
            if message_type == 'subscribe':
                instance_pk = payload.get("instance_pk")
                if instance_pk:
                    async_to_sync(self.channel_layer.group_add)(f'agentInstance_{instance_pk}', self.channel_name)
                return

            if message_type == 'unsubscribe':
                instance_pk = payload.get("instance_pk")
                if instance_pk:
                    async_to_sync(self.channel_layer.group_discard)(f'agentInstance_{instance_pk}', self.channel_name)
                return
            
            # Main message handler dispatch
            handler = MESSAGE_HANDLERS.get(message_type)
            if handler:
                handler(self, **payload)
            else:
                self.send(text_data=json.dumps({'object': 'error', 'message': f'Unknown message type: {message_type}. Available:\n{"\n".join(MESSAGE_HANDLERS.keys())}'}))

        except json.JSONDecodeError:
            self.send(text_data=json.dumps({'object': 'error', 'message': 'Invalid JSON format.'}))
        except Exception as e:
            traceback.print_exc()
            self.send(text_data=json.dumps({'object': 'error', 'message': f'An error occurred: {str(e)}{traceback.format_exc()}'}))

    def agent_message(self, event):
        """
        Generic message handler from the channel layer to push updates to the client.
        """
        self.send(text_data=json.dumps(event['payload']))

# Ensure agent_events handlers are registered
from agents.consumers import agent_events
from agents.consumers import agent_events

# Ensure agent_instance_events handlers are registered
from agents.consumers import agent_instance_events
