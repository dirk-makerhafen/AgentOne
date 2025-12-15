TOOLS = {
    "set": {
        "name": "kv_storage.set",
        "title": "Set kv_storage value",
        "description": "Sets a key-value pair in the shared store. Values must be JSON-serializable strings. Keys without a colon (':') are private to the current agent and are automatically prefixed with 'agent:<agent_id>:'. Namespaced keys (e.g., 'team:my_data') are used as-is.",
        "parameters": {
        "type": "object",
        "properties": {
            "key": {
            "type": "string",
            "description": "The key to set. Naked keys (no colon) are made private via 'agent:<agent_id>:<key>'. Namespaced keys are shared."
            },
            "value": {
            "type": "string",
            "description": "The JSON-serializable string value to store."
            }
        },
        "required": ["key", "value"]
        }
    },

    "get": {
        "name": "kv_storage.get",
        "title": "Get kv_storage value",
        "description": "Retrieves the value associated with a key from the store. Naked keys are automatically prefixed as private keys. Returns a JSON string.",
        "parameters": {
        "type": "object",
        "properties": {
            "key": {
            "type": "string",
            "description": "The key to retrieve. Naked keys are private; namespaced keys are shared."
            }
        },
        "required": ["key"]
        }
    },

    "list": {
        "name": "kv_storage.list",
        "title": "List kv_storage keys",
        "description": "Lists all keys that start with the given prefix. Naked prefixes are made private; namespaced prefixes are shared.",
        "parameters": {
        "type": "object",
        "properties": {
            "prefix": {
            "type": "string",
            "description": "The prefix to filter keys by. Empty string lists all keys."
            }
        },
        "required": ["prefix"]
        }
    },

    "delete": {
        "name": "kv_storage.delete",
        "title": "Delete kv_storage key",
        "description": "Deletes a key-value pair from the store. Naked keys are prefixed automatically; namespaced keys are used as-is.",
        "parameters": {
        "type": "object",
        "properties": {
            "key": {
            "type": "string",
            "description": "The key to delete. Naked keys become private keys."
            }
        },
        "required": ["key"]
        }
    },

    "subscribe": {
        "name": "kv_storage.subscribe",
        "title": "Subscribe to kv_storage key changes",
        "description": "Creates a subscription to receive automatic updates when the specified key changes.",
        "parameters": {
        "type": "object",
        "properties": {
            "key": {
            "type": "string",
            "description": "The key to subscribe to. Naked keys become private keys."
            }
        },
        "required": ["key"]
        }
    },

    "unsubscribe": {
        "name": "kv_storage.unsubscribe",
        "title": "Unsubscribe from kv_storage key changes",
        "description": "Removes a subscription for the specified key.",
        "parameters": {
        "type": "object",
        "properties": {
            "key": {
            "type": "string",
            "description": "The key to unsubscribe from. Naked keys become private keys."
            }
        },
        "required": ["key"]
        }
    }
}
