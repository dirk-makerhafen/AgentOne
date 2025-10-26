
PROMPT_INSTRUCTIONS_old = '''
# Python Tool and VARS Dictionary

**Purpose:** The `python` tool allows you to execute arbitrary Python code. This is mandatory for all deterministic and procedural tasks, including but not limited to:
* Counting
* Arithmetic and Calculations
* Sorting and Filtering
* History Analysis (via the `messages` variable)

**Key Feature: The `VARS` Dictionary**

The `VARS` dictionary is a shared, persistent object accessible within the `python` tool's execution environment.

* **Persistence:** `VARS` data persists across multiple `python` tool calls.
* **Capacity:** It has a 100-value Least Recently Used (LRU) capacity.
* **Management:** You **must** proactively manage `VARS` by calling `del VARS["key"]` for any variables that are no longer needed to prevent unintended eviction of active data.
* **Accessing Values for Chat Output:** To display a `VARS` value in your conversational output to the user, use the Jinja-like syntax: `{% raw %}{{VARS["key"]}}{% endraw %}`.
* **Accessing Values for LLM Reasoning/Internal Use:** To inspect or use a `VARS` value for your internal reasoning or subsequent `python` logic, you **must** `print(VARS["key"])` within the `python` tool's `source` code. The printed output will appear in the `stdout` part of the tool's result, which you can then parse.

**History Analysis with `messages`:**

A special object named `messages` is available within the `python` environment for history analysis.
*  `messages` provides access to `ConversationLogEntry` objects, each with properties like `created_at`, `updated_at`, `role` (e.g., "user", "assistant"), and `message` (the actual text content).
* You can query `messages` using standard django orm operations and methods like `.order_by('-created_at')` for reverse chronological sorting, `.filter(role='user')` to filter by speaker, and list slicing (e.g., `[:10]`) to limit the number of entries.

**Successful Execution Feedback:**

* Upon successful execution, the `python` tool returns a `status: "success"` and an `updated_vars` list. The `updated_vars` list shows the name of any `VARS` keys that were modified during the execution. It will not show the values the these vars directly. When existing, stdout and stderr will contain any output printed by your Python code.

**Example code:**

# Counting 'a's in a string and storing in VARS
VARS['my_string'] = 'example_word'
VARS['a_count'] = VARS['my_string'].count('a')

# Accessing VARS for internal reasoning
print(VARS['a_count'])

# Counting 'a's in the last 5 user messages
user_messages = messages.order_by('-created_at').filter(role='user')[:5]
total_a_in_user_history = sum([entry.message.count('a') for entry in user_messages])
VARS['total_a_history'] = total_a_in_user_history

# Deleting an unused VARS entry
del VARS['my_string']

'''

PROMPT_INSTRUCTIONS = r'''
# Python Tool 

**Purpose:** The `python` tool allows you to execute arbitrary Python code. This is mandatory for all deterministic and procedural tasks, including but not limited to:
* Counting
* Arithmetic and Calculations
* Sorting and Filtering
* History Analysis (via the `messages` variable)

**History Analysis with `messages`:**

A special object named `messages` is available within the `python` environment for history analysis.
*  `messages` provides access to `ConversationLogEntry` objects, each with properties like `created_at`, `updated_at`, `role` (e.g., "user", "assistant"), and `message` (the actual text content).
* You can query `messages` using standard django orm operations and methods like `.order_by('-created_at')` for reverse chronological sorting, `.filter(role='user')` to filter by speaker, and list slicing (e.g., `[:10]`) to limit the number of entries.

**Successful Execution Feedback:**

* Upon successful execution, the `python` tool returns a `status: "success"`. When existing, stdout and stderr will contain any output printed by your Python code.

**Example code:**

my_string = 'example_word'
a_count = my_string.count('a')
print(f"a_count: {a_count}")
# Counting 'a's in the last 5 user messages
user_messages = messages.order_by('-created_at').filter(role='user')[:5]
total_a_in_user_history = sum([entry.message.count('a') for entry in user_messages])
print(f"total_a_in_user_history: {total_a_in_user_history}")
'''

PROMPT_LIST_OF_SHARED_VARS = '''
# Existing keys in your shared VARS dict:
{% for key in keys %}
- {{key | safe}}
{% endfor %}

'''

PROMPTS = [
    {
        "name": "instructions",
        "title": "Python tool instructions",
        "description": "Contains general usage instructions for the python tool",
        "arguments": [],
        'template': PROMPT_INSTRUCTIONS,
    },
    {
        "name": "list_of_shared_vars",
        "title": "Python tool list of vars",
        "description": "todo",
        "arguments": [
            {
                "name": "keys",
                "description": "list of key for VARS dict",
                "required": True,
            }
        ],
        'template': PROMPT_LIST_OF_SHARED_VARS,
    },
]


TOOLS = {
    'python': {
        "name": "python",
        "title": "Execute Python script",
        'description': 'Executes Python source code. Can be run once or as a recurring subscription.',
        "inputSchema": {
            "type": "object",
            'parameters': {
                'source': {
                    'type': 'string',
                    'description': 'The Python source code to run.',
                    'required': True,
                },
                'subscription_id': {
                    'type': 'string',
                    'description': "A unique identifier for the subscription if mode is 'subscribe'. This will be used to unsubscribe later.",
                    'required': False,
                },
                'mode': {
                    'type': 'string',
                    'enum': ['one-shot', 'subscribe'],
                    'description': "Execution mode: 'one-shot' executes the code once (default), 'subscribe' executes it before every LLM query.",
                    'required': False,
                    'default': 'one-shot',
                },
            },
            "required" : ["source"],
        }
    }
}

