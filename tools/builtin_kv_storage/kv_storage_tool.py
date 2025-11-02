import json
import traceback
from agents.models.llm_query import QueryMessagePart
from tools.builtin_kv_storage.models.kv_item import KVItem
from core.models.prompt import Prompt
from tools.base.base_tool import BaseTool
from tools.builtin_subscriptions.models.tool_subscription import ToolSubscription
from .apps import ToolsBuiltinKvStorageConfig

from .prompts import TOOLS, PROMPTS


class KVStorageTool(BaseTool):
    DESCRIPTION = "Manages a shared key-value store for inter-agent communication and state management."
    TOOLS = TOOLS
    PROMPTS = PROMPTS

    def get_header_parts(self):
        instructionsTemplate = Prompt.get_template(self.agentInstance, source=ToolsBuiltinKvStorageConfig.name, key="instructions")
        functionsTemplate = Prompt.get_template(self.agentInstance, source=ToolsBuiltinKvStorageConfig.name   , key="functions")
        return [
            QueryMessagePart(promptVariant=instructionsTemplate, tags=["Prompts", "KVStorage"]),
            QueryMessagePart(promptVariant=functionsTemplate   , tags=["Prompts", "KVStorage"])
        ]
        #return [
        #    {"tpId": instructionsTemplate.pk, "tags": ["Prompts", "KVStorage"], "data":{}},
        #    {"tpId": functionsTemplate.pk, "tags": ["Prompts", "KVStorage"], "data":{}},
        #]

    def get_effective_key(self, key, agent_instance_id):
        """
        Determines the effective key based on whether it's a naked key or namespaced.
        Naked keys are automatically prefixed with 'agent:<agent_instance_id>:'.
        """
        if ':' not in key:
            return f"agent:{agent_instance_id}:{key}"
        return key

    def set(self, toolCall, key: str, value: str):
        """
        Sets a key-value pair in the shared store.
        Values must be JSON-serializable strings.
        Naked keys (without ':') are automatically prefixed with 'agent:<agent_id>:'.
        Args:
            key (str): The key to set.
            value (str): The value to store (must be a JSON string).
        """
        try:
            # Ensure value is valid JSON
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            message = f"Value for key '{key}' is not a valid JSON string."
            return (False, {"status": "error", "message": message})

        try:
            agent = toolCall.agentInstance
            effective_key = self.get_effective_key(key, agent.pk)

            kv_item, created = KVItem.objects.update_or_create(
                key=effective_key,
                defaults={'value': parsed_value, 'agent': agent}
            )
            if created:
                message = f"Key '{key}' set (effective: '{effective_key}')."
                return (True, {"status": "success", "message": message})
            else:
                message = f"Key '{key}' updated (effective: '{effective_key}')."
                return (True, {"status": "success", "message": message})
        except Exception as e:
            message = f"An unexpected error occurred while setting key '{key}': {type(e).__name__}: {e}\n{traceback.format_exc()}"
            return (False, {"status": "error", "message": message})

    def get(self, toolCall, key: str):
        """
        Retrieves the value associated with a key from the shared store.
        Naked keys (without ':') are automatically prefixed with 'agent:<agent_id>:'.
        Args:
            key (str): The key to retrieve.
        Returns:
            tuple: (success_bool, dict_result) where dict_result contains status, message, and 'value' if successful.
        """
        agent_instance_id = toolCall.agentInstance.pk
        effective_key = self.get_effective_key(key, agent_instance_id)

        try:
            kv_item = KVItem.objects.get(key=effective_key)
            message = f"Retrieved key '{key}' (effective: '{effective_key}')."
            return (True, {"status": "success", "message": message, "value": json.dumps(kv_item.value)})
        except KVItem.DoesNotExist:
            message = f"Key '{key}' (effective: '{effective_key}') not found."
            return (False, {"status": "error", "message": message})
        except Exception as e:
            message = f"An unexpected error occurred while getting key '{key}': {type(e).__name__}: {e}\n{traceback.format_exc()}"
            return (False, {"status": "error", "message": message})

    def list(self, toolCall, prefix: str = ""):
        """
        Lists all keys in the store that start with the given prefix.
        Naked prefixes (without ':') are automatically prefixed with 'agent:<agent_id>:'.
        Args:
            prefix (str): The prefix to filter keys by. An empty string lists all keys.
        Returns:
            tuple: (success_bool, dict_result) where dict_result contains status, message, and 'keys' (a JSON array) if successful.
        """
        agent_instance_id = toolCall.agentInstance.pk
        
        # Adjust prefix for naked vs. namespaced logic, similar to get_effective_key
        if prefix and ':' not in prefix:
            effective_prefix = f"agent:{agent_instance_id}:{prefix}"
        else:
            effective_prefix = prefix

        try:
            matching_keys = list(KVItem.objects.filter(key__startswith=effective_prefix).values_list('key', flat=True))
            message = f"Listed keys with prefix '{prefix}' (effective: '{effective_prefix}'). Found {len(matching_keys)} items."
            return (True, {"status": "success", "message": message, "keys": json.dumps(matching_keys)})
        except Exception as e:
            message = f"An unexpected error occurred while listing keys with prefix '{prefix}': {type(e).__name__}: {e}\n{traceback.format_exc()}"
            return (False, {"status": "error", "message": message})

    def delete(self, toolCall, key: str):
        """
        Deletes a key-value pair from the shared store.
        Naked keys (without ':') are automatically prefixed with 'agent:<agent_id>:'.
        Args:
            key (str): The key to delete.
        Returns:
            tuple: (success_bool, dict_result) where dict_result contains status and message.
        """
        agent_instance_id = toolCall.agentInstance.pk
        effective_key = self.get_effective_key(key, agent_instance_id)

        try:
            deleted_count, _ = KVItem.objects.filter(key=effective_key).delete()
            if deleted_count > 0:
                message = f"Key '{key}' (effective: '{effective_key}') deleted successfully."
                return (True, {"status": "success", "message": message})
            else:
                message = f"Key '{key}' (effective: '{effective_key}') not found for deletion."
                return (False, {"status": "error", "message": message})
        except Exception as e:
            message = f"An unexpected error occurred while deleting key '{key}': {type(e).__name__}: {e}\n{traceback.format_exc()}"
            return (False, {"status": "error", "message": message})    
        
    def get_history_limiting_rules(self):
        limit = self.agentInstance.effective_limit_max_conversation_messages
        return [
            {
                'group_name': "KVStorage",
                'name': 'key,function',
                'description': 'Limits history on a per-key, per-function basis (e.g., max 2 gets for "my:key").',
                'match': lambda tc: tc.function_name in ['get', 'set', 'delete'],
                'key': lambda tc: (tc.arguments.get('key', ''), tc.function_name),
                'limits': {'pending': limit, 'success': 2, 'failed': 1, 'max': 2}
            },
            {
                'group_name': "KVStorage",
                'name': 'prefix,function',
                'description': 'Limits history on a per-prefix basis for the list function.',
                'match': lambda tc: tc.function_name == 'list',
                'key': lambda tc: (tc.arguments.get('prefix', ''), tc.function_name),
                'limits': {'pending': limit, 'success': 2, 'failed': 1, 'max': 2}
            },
            {
                'group_name': "KVStorage",
                'name': 'any',
                'description': 'A general fallback limit for all kv_storage operations.',
                'match': lambda tc: tc.function_name in ['get', 'set', 'list', 'delete'],
                'key': lambda tc: '',
                'limits': {'pending': limit, 'success': limit, 'failed': 2, 'max': limit}
            }
        ]
    
    def subscribe(self, toolCall, key: str):
            """
            Creates a new subscription for a specific KVStore key. This allows an agent to be notified of changes to the key.
            The subscription_id must be unique for the agent instance.
            Args:
                key (str): The KVStore key to subscribe to.
                subscription_id (str): A unique identifier for this subscription. If None, one will be generated.
            Returns:
                tuple: (success_bool, dict_result) where dict_result contains status, message, and the generated/used subscription_id.
            """
            agent_instance_id = toolCall.agentInstance.pk
            effective_key = self.get_effective_key(key, agent_instance_id)
            subscription_id = f"kv_storage:{effective_key}"
            ToolSubscription.objects.update_or_create(
                agentInstance=self.agentInstance,
                subscription_id=subscription_id,
                defaults={
                    'agent': self.agentInstance.agent,
                    'creating_tool_call': toolCall,
                    'tool_name': 'kv',
                    'arguments': { "key": key },
                    'is_active': True
                }
            )
            try:
                message = f"Subscription for key '{key}' (effective: '{effective_key}')"
                return (True, {"status": "success", "message": message, "subscription_id": subscription_id})
            except Exception as e:
                message = f"An unexpected error occurred while subscribing to key '{key}': {type(e).__name__}: {e}\n{traceback.format_exc()}"
                return (False, {"status": "error", "message": message})
            
    def unsubscribe(self, toolCall, key: str):
        agent_instance_id = toolCall.agentInstance.pk
        effective_key = self.get_effective_key(key, agent_instance_id)
        subscription_id = f"kv_storage:{effective_key}"
        try:
            subscription = ToolSubscription.objects.get(agentInstance=self.agentInstance, subscription_id=subscription_id, is_active=True)
            subscription.is_active = False
            subscription.save()
            return (True, {"status": "success", "message": f"Subscription '{subscription_id}' has been successfully unsubscribed."})
        except ToolSubscription.DoesNotExist:
            return (False, {"status": "error", "message": f"No active subscription found with ID '{subscription_id}'."})
        except Exception as e:
            return (False, {"status": "error", "message": f"An unexpected error occurred: {str(e)} {traceback.format_exc()}"})
