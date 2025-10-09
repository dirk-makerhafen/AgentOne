import traceback
import functools
import traceback
import requests

def dispatched_primitive_operation(func):
    """
    A decorator that intercepts a function call and dispatches it
    for either local or remote execution based on the agentInstance's system configuration.
    The wrapper function created by this decorator will have the signature: wrapper(agentInstance, **kwargs)
    """

    def _run_local(func, **kwargs):
        try:
            return func(**kwargs)
        except Exception as e:
            return {'status': 'error', 'message': f"Local execution error in '{func.__name__}': {str(e)} {traceback.format_exc()}"}

    def _run_remote(system, func, **kwargs):
        try:
            response = requests.post(
                url = f"{system.executor_url.rstrip('/')}/python", 
                json= {
                    "source": f'FUNC_RESULT={func.__name__}(**kwargs)', 
                    "locals_dict": { "kwargs": kwargs }, 
                    "locals_to_return":["FUNC_RESULT", "VARS"]
                }, 
                headers={ 
                    'X-API-Key': system.executor_api_key, 
                    'Content-Type': 'application/json'
                }, 
                timeout=70
            )
            response.raise_for_status()
            return response.json().get("vars",{}).get("FUNC_RESULT", response.json())
        except Exception as e:
            return {'status': 'error', 'message': f"Remote dispatch error for '{func.__name__}': {str(e)} {traceback.format_exc()}"}

    @functools.wraps(func)
    def wrapper(agentInstance=None, system=None, **kwargs): # Added 'system' argument
        is_remote = False
        target_system = None

        if system: # Prioritize system if explicitly passed
            target_system = system
        elif agentInstance: # Fallback to agentInstance.system
            target_system = agentInstance.system

        if target_system:
            is_remote = target_system.is_remote_executor and target_system.executor_url and target_system.executor_api_key

        if is_remote:
            return _run_remote(system=target_system, func=func, **kwargs)
        return _run_local(func=func, **kwargs)
         
    return wrapper
