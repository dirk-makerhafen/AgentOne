import traceback
import functools
import traceback
import requests

def dispatched_inprocess(func):
    @functools.wraps(func)
    def wrapper(*args, agentInstance=None, system=None, **kwargs): # Added 'system' argument
        is_remote = False
        target_system = None
        if system: # Prioritize system if explicitly passed
            target_system = system                
        elif agentInstance: # Fallback to agentInstance.system
            target_system = agentInstance.system
        if target_system:
            is_remote = target_system.executor_mode != "local"
        if is_remote:
            return _run_remote_inprocess(*args, system=target_system, func=func, **kwargs)
        return _run_local(*args, func=func, **kwargs)
    return wrapper

def dispatched_detached(func):
    @functools.wraps(func)
    def wrapper(*args, agentInstance=None, system=None, **kwargs): # Added 'system' argument
        is_remote = False
        target_system = None
        if system: # Prioritize system if explicitly passed
            target_system = system                
        elif agentInstance: # Fallback to agentInstance.system
            target_system = agentInstance.system
        if target_system:
            is_remote = target_system.executor_mode != "local"
        if is_remote:
            return _run_remote_detached(*args, system=target_system, func=func, **kwargs)
        return _run_local(*args, func=func, **kwargs)
    return wrapper

def _run_local(*args, func, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        return {'status': 'error', 'message': f"Local execution error in '{func.__name__}': {str(e)} {traceback.format_exc()}"}

def _run_remote_detached(*args, func, system, **kwargs):
    try:
        response = requests.post(
            url = f"{system.executor_url.rstrip('/')}/python", 
            json = {
                "source": f'FUNC_RESULT={func.__name__}(*args, **kwargs)', 
                "locals_dict": { "kwargs": kwargs, "args": args[1:] }, 
                "locals_to_return":["FUNC_RESULT", "VARS"]
            }, 
            headers = { 
                'X-API-Key': system.executor_api_key, 
                'Content-Type': 'application/json'
            }, 
            timeout = 70
        )
        response.raise_for_status()
        return response.json().get("vars",{}).get("FUNC_RESULT", response.json())
    except Exception as e:
        return {'status': 'error', 'message': f"Remote dispatch error for '{func.__name__}': {str(e)} {traceback.format_exc()}"}

def _run_remote_inprocess(*args, func, system, **kwargs):
    try:
        response = requests.post(
            url = f"{system.executor_url.rstrip('/')}/direct", 
            json= {
                "function_name": func.__name__,
                "kwargs": kwargs
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
