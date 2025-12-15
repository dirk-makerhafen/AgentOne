from tools.base.prompts import TOOL_RESPONSE_MARKER

PROMPT_INSTRUCTIONS = """
# Tool Subscriptions for Advanced Situational Awareness

Subscriptions give you live, auto-updating context. Instead of static snapshots, you attach recurring commands that refresh before every prompt.
You can execute any `shell` command or `python` script with `mode='subscribe'`. You must provide a unique `subscription_id` to name and track this subscription.
The system will then **re-run this command before every new prompt is sent to you** and inject the fresh output directly into your context.
When you no longer need a subscription, you clean it up with `unsubscribe(subscription_id='find_main_container_css')`.

## Example
@@@shell(source="grep -r .main-container . --include '*.css' -n", mode='subscribe', subscription_id='find_main_container_css')@@@

## Advanced Usage
This is not just a search tool. It is a generic mechanism for maintaining situational awareness. Think of tool subscriptions as your own set of customizable "senses."

- Code Navigation & Analysis:
  Task: You need to modify a UI component but don't know where its styles are defined.
  Subscription: `shell(source="grep -r 'class-name' . -n", mode='subscribe', subscription_id='find_styles')`
  Benefit: You get a persistent list of all relevant files. As you make changes, you can be confident you aren't missing any instances.

- State Tracking:
  Task: You are working on a feature and need to track the number of "TODO" comments remaining in the code.
  Subscription: `python(source=\"\"\"
import os
todo_count = 0
for root, _, files in os.walk('.'):
    for file in files:
        if file.endswith('.py'):
            try:
                with open(os.path.join(root, file)) as f:
                    todo_count += f.read().count('TODO:')
            except Exception:
                pass
print(f"Remaining TODOs: {todo_count}")
\"\"\", mode='subscribe', subscription_id='todo_counter')`
  Benefit: You have a live, custom metric for your task progress, updated automatically.

- Log Monitoring:
  Task: You are debugging a service and need to watch for errors in its log file.
  Subscription: `shell(source="tail -n 15 /var/log/my_app.log", mode='subscribe', subscription_id='watch_app_log')`
  Benefit: You get a live feed of the latest log entries without using `fs_load` on a growing file.

  
## Best Practices
1.  Use Descriptive IDs: Choose a `subscription_id` that clearly describes its purpose (e.g., `'find_user_model_refs'` instead of `'sub1'`).
2.  Unsubscribe Proactively: As soon as a subscription is no longer relevant to your current task, `unsubscribe` from it. This keeps your context clean, relevant, and token-efficient.
3.  Keep Commands Efficient: Subscriptions run before every query. Favor fast, targeted commands (`grep`, `find`) over slow, complex scripts that might delay your response time.
"""



PROMPT_SUBSCRIPTION_RESULT_INJECTION = """
# The following is the output of a recurring command subscription you created.
# Subscription ID: {{subscription_id}}
# Status: {{status}}
# Command: {{tool_name}}({{arguments | safe}})
<%(marker)s function='{{tool_name}}' subscription_id='{{subscription_id}}' status='{{status}}'>
{{output | safe}}
</%(marker)s>
""" % {"marker":TOOL_RESPONSE_MARKER}


PROMPTS = [
    {
        "name": "instructions",
        "title": "Subscriptions tool instructions",
        "description": "",
        "arguments": [],
        'template': PROMPT_INSTRUCTIONS,
    },
    {
        "name": "subscription_result_injection",
        "title": "TODO",
        "description": "TODO",
        "arguments": [],
        'template': PROMPT_SUBSCRIPTION_RESULT_INJECTION,
    },
]

TOOLS = {
    "unsubscribe": {
        "name": "unsubscribe",
        "title": "Unsubscribe from Tool subscription",
        "description": "Removes an active tool subscription, stopping it from being executed before future LLM queries.",
        "parameters": {
            "type": "object",
            "properties": {
                "subscription_id": {
                    "type": "string",
                    "description": "The unique identifier of the subscription to be removed.",
                }
            },
            "required" : ["subscription_id"],
        }
    }
}
