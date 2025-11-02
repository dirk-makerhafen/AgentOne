TOOLS = {
    "set": {
        "name": "kv_storage.set",
        "title": "Set kv_storage value",
        "description": "Sets a key-value pair in the shared store. Values must be JSON-serializable strings. Keys without a colon (':') are private to the current agent, otherwise they are used as-is for shared namespaces.",
        "inputSchema": {
            "type": "object",
            "parameters": {
                "key": {"type": "string", "description": "The key to set. Naked keys (without ':') are private and automatically prefixed with 'agent:<agent_id>:'. Namespaced keys (e.g., 'team:my_data') are shared.",  "required": True},
                "value": {"type": "string", "description": "The value to store, must be a JSON string.", "required": True}
            },
            "required" : ["key", "value"],
        },
    },
    "get": {
        "name": "kv_storage.get",
        "title": "Get kv_storage value",
        "description": "Retrieves the value associated with a key from the shared store. Returns the value as a JSON string, or an error if not found. Naked keys (without ':') are private to the current agent, otherwise they are used as-is for shared namespaces.",
        "inputSchema": {
            "type": "object",
            "parameters": {
                "key": {"type": "string", "description": "The key to retrieve. Naked keys (without ':') are private and automatically prefixed with 'agent:<agent_id>:'. Namespaced keys (e.g., 'team:my_data') are shared.", "required": True}
            },
            "required" : ["key"],
        }
    },
    "list": {
        "name": "kv_storage.list",
        "title": "List kv_storage keys",
        "description": "Lists all keys in the store that start with the given prefix. Returns a JSON array of matching keys. Naked prefixes (without ':') are private to the current agent, otherwise they are used as-is for shared namespaces.",
        "inputSchema": {
            "type": "object",
            "parameters": {
                "prefix": {"type": "string", "description": "The prefix to filter keys by. An empty string lists all keys. Naked prefixes (without ':') are private and automatically prefixed with 'agent:<agent_id>:'. Namespaced prefixes (e.g., 'team:my_data') are shared.", "required": True},
            },
            "required" : ["prefix"],
        }
    },
    "delete": {
        "name": "kv_storage.delete",
        "title": "Delete kv_storage key",
        "description": "Deletes a key-value pair from the shared store. Naked keys (without ':') are private to the current agent, otherwise they are used as-is for shared namespaces.",
        "inputSchema": {
            "type": "object",
            "parameters": {
                "key": {"type": "string", "description": "The key to delete. Naked keys (without ':') are private and automatically prefixed with 'agent:<agent_id>:'. Namespaced keys (e.g., 'team:my_data') are shared.", "required": True},
            },
            "required" : ["key"],
        }
    },
    "subscribe": {
        "name": "kv_storage.subscribe",
        "title": "Subscribe to kv_storage key changes",
        "description": "Creates a new subscription for a specific KVStore key. This allows an agent to be notified of changes to the key. ",
        "inputSchema": {
            "type": "object",
            "parameters": {
                "key": {"type": "string", "description": "The KVStore key to subscribe to.", "required": True},
            },
            "required": ["key"],
        }
    },
    "unsubscribe": {
        "name": "kv_storage.unsubscribe",
        "title": "Unsubscribe from kv_storage key changes",
        "description": "Removes an active subscription for a KVStore key.",
        "inputSchema": {
            "type": "object",
            "parameters": {
                "key": {"type": "string", "description": "The key of the subscription to be removed.", "required": True}
            },
            "required": ["key"],
        }
    },
}

PROMPTS = [
    {
        "name": "instructions",
        "template": """The `kv_storage` tool provides a shared key-value store for agents to manage state and communicate.

Key Conventions:
- **Private Keys:** Keys without a colon (`:`) are considered "naked" (e.g., "my_status"). These are automatically prefixed with `agent:<your_agent_id>:` by the tool, making them private to your specific agent instance.
- **Shared Keys:** Keys containing a colon (e.g., "team:project_status", "resources:api_endpoint") are used as-is, allowing for shared namespaces by convention. Use these for inter-agent communication and global resources.

Value Format:
- All values stored and retrieved must be JSON-serializable strings. When setting a value, provide a valid JSON string (e.g., `'{"status": "active"}'`). When retrieving, you will receive a JSON string that you can parse.

Purpose:
- Use `kv_storage.set` to store information.
- Use `kv_storage.get` to retrieve information.
- Use `kv_storage.list` to discover keys (e.g., other agents' registered data).
- Use `kv_storage.delete` to remove outdated information.

**Subscription Functions for Advanced Situational Awareness:**
- Use `kv_storage.subscribe` to create live, auto-updating subscriptions that provide real-time context
- Use `kv_storage.unsubscribe` to remove subscriptions when no longer needed

Example Usage for Agent Registration and Discovery:
- To register yourself for other agents to discover:
  `kv_storage.set(key="team:agents:<your_agent_id>:info", value='{"name": "<your_agent_name>", "purpose": "<your_purpose>"}')`
- To discover other agents:
  `kv_storage.list(prefix="team:agents:")`
- To get information about a specific agent:
  `kv_storage.get(key="team:agents:30:info")`
- To create a subscription for monitoring:
  `kv_storage.subscribe(key="team:agents:30:info")`
- To remove a subscription:
  `kv_storage.unsubscribe(key="team:agents:30:info")`
"""
    }
]
