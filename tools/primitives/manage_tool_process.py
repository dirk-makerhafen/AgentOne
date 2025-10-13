from ._dispatch_decorator import dispatched_inprocess
import asyncio
import traceback

# Global state for managing long-running tool processes launched by this executor.
# Key: process_id (string), Value: dict containing the live async session and context managers.
managed_processes = {}

# Global state for the asyncio event loop running in a background thread
_async_loop = None
_loop_thread = None


@dispatched_inprocess
def start_tool_process(
    process_id: int, 
    command: str = None, 
    args: list = None,
    cwd: str = None, 
    env: dict = None,
    tool_config: dict = None, # For starting the client
):
    try:
        loop = _get_async_loop()
        coro = _start_tool_process_async(process_id, command, args, cwd, env, tool_config)
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        result = future.result(timeout=60)  # Add a timeout for safety
        return result
    except Exception as e:
        return {'status': 'error', 'message': f"An error occurred in start_tool_process: {type(e).__name__}: {e}\n{traceback.format_exc()}"}

async def _start_tool_process_async(
    process_id: int, 
    command: str = None, 
    args: list = None,
    cwd: str = None, 
    env: dict = None,
    tool_config: dict = None,
):
    """
    The core async logic for managing tool processes. This function uses AsyncExitStack
    to robustly manage the lifecycle of MCP clients, creating persistent, stateful 
    connections that can be used across multiple calls.
    """
    global managed_processes
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from contextlib import AsyncExitStack
    import traceback
    import sys  # Import sys to access __stderr__

    # Clean up any previous, orphaned instance for this process_id before starting a new one.
    if process_id in managed_processes:
        old_client_info = managed_processes.pop(process_id)
        try:
            await old_client_info['exit_stack'].aclose()
        except Exception:
            pass # Ignore errors during cleanup of potentially broken clients

    if not all([command, cwd, tool_config]):
        return {'status': 'error', 'message': "'command', 'cwd', and 'tool_config' are required for start."}

    exit_stack = AsyncExitStack()
    try:
        # Pass the original, pre-redirected stderr stream to the subprocess.
        # This ensures it has a valid fileno and its output goes to the console.
        server_params = StdioServerParameters(command=command, args=args or [], cwd=cwd, env=env)
        stdio_transport = await exit_stack.enter_async_context(stdio_client(server_params, errlog=sys.__stderr__))
        read, write = stdio_transport

        session = await exit_stack.enter_async_context(ClientSession(read, write))

        # Perform the handshake to ensure the tool is ready.
        await session.initialize()

        # Store the active session and the exit_stack in our global state.
        # The exit_stack holds the context for both the session and the underlying process.
        managed_processes[process_id] = {
            'session': session,
            'exit_stack': exit_stack,
        }
        return {'status': 'success', 'message': f'Client {process_id} started and initialized successfully.'}
    except Exception as e:
        # If starting fails, the exit_stack will automatically clean up any partially opened resources.
        await exit_stack.aclose()
        return {'status': 'error', 'message': f"Failed to start client {process_id}: {e}\n{traceback.format_exc()}"}


@dispatched_inprocess
def stop_tool_process(process_id: int):
    try:
        loop = _get_async_loop()
        coro = _stop_tool_process_async(process_id)
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        result = future.result(timeout=60)  # Add a timeout for safety
        return result
    except Exception as e:
        return {'status': 'error', 'message': f"An error occurred in stop_tool_process: {type(e).__name__}: {e}\n{traceback.format_exc()}"}

async def _stop_tool_process_async(process_id: int):
    global managed_processes
    client_info = managed_processes.pop(process_id, None)
    if client_info:
        try:
            # Gracefully shut down the client by closing the exit_stack.
            await client_info['exit_stack'].aclose()
            return {'status': 'success', 'message': f'Client {process_id} stopped.'}
        except Exception as e:
            return {'status': 'warning', 'message': f'Error during client stop for {process_id}: {e}'}
    return {'status': 'success', 'message': f'Client {process_id} was not running.'}


@dispatched_inprocess
def call_tool_session(process_id: int, function_name: str, kwargs: dict = {}, args: list = []):
    try:
        loop = _get_async_loop()
        coro = _call_tool_session_async(process_id, function_name, kwargs, args)
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        result = future.result(timeout=60)  # Add a timeout for safety
        return result
    except Exception as e:
        return {'status': 'error', 'message': f"An error occurred in call_tool_session: {type(e).__name__}: {e}\n{traceback.format_exc()}"}

async def _call_tool_session_async(process_id: int, function_name: str, kwargs: dict = {}, args: list = []):
    global managed_processes
    if process_id not in managed_processes: return {'status': 'error', 'message': f'Client {process_id} not found or not running.'}
    session = managed_processes[process_id]['session']
    result = await getattr(session, function_name)(*args, **kwargs)
    print(result)
    if result:
        return {'status': 'success', 'data': result.dict()}
    return {'status': 'success', 'data': None}



# HELPER FUNCTIONS 
def _get_async_loop():
    """Starts and returns the global asyncio event loop running in a background thread."""
    global _async_loop, _loop_thread
    if _loop_thread is None:
        import asyncio
        import threading
        print("Starting new event loop")
        _async_loop = asyncio.new_event_loop()
        _loop_thread = threading.Thread(target=_async_loop.run_forever, daemon=True)
        _loop_thread.start()
    return _async_loop


