from ._dispatch_decorator import dispatched_primitive_operation

# Global state for managing long-running tool processes launched by this executor.
# Key: process_id (string), Value: dict containing the live async session and context managers.
managed_processes = {}

# Global state for the asyncio event loop running in a background thread
_async_loop = None
_loop_thread = None

@dispatched_primitive_operation
def manage_tool_process(
    action: str, 
    process_id: str, 
    command: str = None, 
    args: list = None,
    cwd: str = None, 
    env: dict = None,
    tool_config: dict = None, # For starting the client
    tool_name: str = None, # For invoking a tool
    tool_kwargs: dict = None # For invoking a tool
):
    """
    Manages the lifecycle and interaction with stateful MCP clients on the executor
    by submitting async tasks to a persistent, thread-safe event loop.
    """
    import asyncio
    import traceback
    try:
        loop = _get_async_loop()
        coro = _manage_tool_process_async(
            action, process_id, command, args, cwd, env, tool_config, tool_name, tool_kwargs
        )
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        result = future.result(timeout=60)  # Add a timeout for safety
        return result
    except Exception as e:
        return {'status': 'error', 'message': f"An error occurred in manage_tool_process (action: {action}): {type(e).__name__}: {e}\n{traceback.format_exc()}"}



def _get_async_loop():
    """Starts and returns the global asyncio event loop running in a background thread."""
    global _async_loop, _loop_thread
    if _loop_thread is None:
        import asyncio
        import threading
        _async_loop = asyncio.new_event_loop()
        _loop_thread = threading.Thread(target=_async_loop.run_forever, daemon=True)
        _loop_thread.start()
    return _async_loop



async def _manage_tool_process_async(
    action: str, 
    process_id: str, 
    command: str = None, 
    args: list = None,
    cwd: str = None, 
    env: dict = None,
    tool_config: dict = None,
    tool_name: str = None,
    tool_kwargs: dict = None
):
    """
    The core async logic for managing tool processes. This function manually handles async context 
    managers to create a persistent, stateful connection that can be used across multiple calls.
    """
    global managed_processes
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import traceback

    if action == 'start':
        # Clean up any previous, orphaned instance for this process_id before starting a new one.
        if process_id in managed_processes:
            old_client_info = managed_processes.pop(process_id)
            try:
                await old_client_info['session_cm'].__aexit__(None, None, None)
                await old_client_info['stdio_cm'].__aexit__(None, None, None)
            except Exception:
                pass # Ignore errors during cleanup of potentially broken clients

        if not all([command, cwd, tool_config]):
            return {'status': 'error', 'message': "'command', 'cwd', and 'tool_config' are required for start."}

        try:
            server_params = StdioServerParameters(command=command, args=args or [], cwd=cwd, env=env)
            
            # Manually enter the async context managers to keep them alive beyond this single 'start' call.
            # This is the core of creating a persistent connection.
            stdio_cm = stdio_client(server_params)
            read, write = await stdio_cm.__aenter__()
            
            session_cm = ClientSession(read, write)
            session = await session_cm.__aenter__()
            
            # Perform the handshake to ensure the tool is ready.
            await session.initialize()
            
            # Store the active session and the context managers in our global state dictionary.
            # This allows subsequent actions ('list_tools', 'invoke_tool') to find and use this connection.
            managed_processes[process_id] = {
                'session': session,
                'session_cm': session_cm,
                'stdio_cm': stdio_cm,
            }
            return {'status': 'success', 'message': f'Client {process_id} started and initialized successfully.'}
        except Exception as e:
            # If starting fails, ensure we clean up any partially created contexts.
            if 'session_cm' in locals() and hasattr(session_cm, '__aexit__'):
                await session_cm.__aexit__(None, None, None)
            if 'stdio_cm' in locals() and hasattr(stdio_cm, '__aexit__'):
                await stdio_cm.__aexit__(None, None, None)
            return {'status': 'error', 'message': f"Failed to start client {process_id}: {e}\n{traceback.format_exc()}"}

    elif action == 'stop':
        client_info = managed_processes.pop(process_id, None)
        if client_info:
            try:
                # Explicitly exit the contexts in reverse order of creation to gracefully shut down.
                await client_info['session_cm'].__aexit__(None, None, None)
                await client_info['stdio_cm'].__aexit__(None, None, None)
                return {'status': 'success', 'message': f'Client {process_id} stopped.'}
            except Exception as e:
                return {'status': 'warning', 'message': f'Error during client stop for {process_id}: {e}'}
        return {'status': 'success', 'message': f'Client {process_id} was not running.'}

    elif action == 'list_tools':
        if process_id not in managed_processes: return {'status': 'error', 'message': f'Client {process_id} not found or not running.'}
        session = managed_processes[process_id]['session']
        result = await session.list_tools()
        return {'status': 'success', 'data': result.model_dump() if result else {}}

    elif action == 'invoke_tool':
        if process_id not in managed_processes: return {'status': 'error', 'message': f'Client {process_id} not found or not running.'}
        if not tool_name: return {'status': 'error', 'message': "'tool_name' is required."}
        session = managed_processes[process_id]['session']
        result = await session.call_tool(tool_name, arguments=tool_kwargs or {})
        if result and result.content:
            return {'status': 'success', 'data': [item.model_dump() for item in result.content]}
        return {'status': 'success', 'data': None}

    else:
        return {'status': 'error', 'message': f'Unknown action: {action}'}
