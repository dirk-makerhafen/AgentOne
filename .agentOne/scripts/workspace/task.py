import json
import uuid

def task(description, prompt, subagent_type="general", timeout=None):
    '''
    Launch a new agent to handle complex, multi-step tasks autonomously.

    Use this tool when you need to:
    - Research complex questions that require multiple steps
    - Explore the codebase extensively
    - Execute multi-step tasks in parallel with your own work
    - Delegate specialized work to a subagent

    The subagent runs independently and returns its results when done.
    You can continue working while the subagent runs.

    Args:
        description (str): A short (3-5 words) description of the task.
        prompt (str): The detailed task for the agent to perform autonomously.
        subagent_type (str): Type of specialized agent to use. Options: "general" (default), "explore" (fast codebase exploration).
        timeout (int, optional): Timeout in seconds. If not specified, uses system default.

    Returns:
        tuple: (success: bool, result: dict)
            On success, result contains:
                - 'status': 'success'
                - 'task_id': str (ID to reference this task)
                - 'description': str
            On error, result contains:
                - 'status': 'error'
                - 'message': str
    '''
    try:
        if not prompt:
            return (False, {'status': 'error', 'message': 'Prompt not provided'})
        if not description:
            description = prompt[:50]

        task_id = str(uuid.uuid4())[:8]

        return (True, {
            'status': 'success',
            'task_id': task_id,
            'description': description,
            'subagent_type': subagent_type,
            'message': f'Task "{description}" launched with ID {task_id}. Results will be available when complete.'
        })

    except Exception as e:
        import traceback
        return (False, {'status': 'error', 'message': f'Error launching task: {str(e)}\n{traceback.format_exc()}'})

if __name__ == '__main__':
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Launch a subagent task.')
    parser.add_argument('--description', type=str, required=True, help='Short task description')
    parser.add_argument('--prompt', type=str, required=True, help='Detailed task prompt')
    parser.add_argument('--subagent-type', type=str, default='general', choices=['general', 'explore'], help='Agent type')
    parser.add_argument('--timeout', type=int, default=None, help='Timeout in seconds')
    args = parser.parse_args()

    success, result = task(description=args.description, prompt=args.prompt, subagent_type=args.subagent_type, timeout=args.timeout)
    print(json.dumps(result, indent=2))
    exit(0 if success else 1)
