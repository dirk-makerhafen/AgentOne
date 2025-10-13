import os
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
from fastapi import FastAPI, Depends, HTTPException, status, Security
from tools.primitives.run_python_code import run_python_code
from tools.primitives.run_shell_script import run_shell_script
from tools.primitives import start_tool_process, stop_tool_process, call_tool_session
import json
import sys
import socket

# --- Configuration Loading ---
# This script expects APIKEY, HOSTNAME, LISTEN, and PORT to be set as environment variables.
APIKEY = os.environ.get("CARNA_CLIENT_API_KEY", "")
HOSTNAME = os.environ.get("CARNA_CLIENT_NAME", socket.gethostname())
LISTEN = os.environ.get("CARNA_CLIENT_LISTEN", "0.0.0.0")
PORT = int(os.environ.get("CARNA_CLIENT_PORT", 8123))

if not APIKEY:
    print("FATAL: CARNA_CLIENT_API_KEY environment variable not set. Cannot start.")
    sys.exit(1)

class ScriptExecution(BaseModel):
    source: str
    locals_dict: dict = {}
    locals_to_return: list = []

class ShellExecution(BaseModel):
    command: str
    env: dict[str, str] = {}
    timeout: int = 60

class DirectExecution(BaseModel):
    function_name: str
    kwargs: dict

app = FastAPI(title=HOSTNAME, description="A lightweight agent for remote python and shell execution.", version="1.0.0")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key == APIKEY:
        return api_key
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Could not validate credentials")

@app.get("/", dependencies=[Depends(get_api_key)])
async def root():
    return {"status": "ok", "name": HOSTNAME, "port": PORT, "listen": LISTEN}

@app.post("/shell", dependencies=[Depends(get_api_key)])
async def execute_shell_command(item: ShellExecution):
    result = run_shell_script(command=item.command, env=item.env, timeout=item.timeout)
    return JSONResponse(content=result)

@app.post("/python", dependencies=[Depends(get_api_key)])
async def execute_python_code(item: ScriptExecution):
    result = run_python_code(python_code_string = item.source, locals_dict=item.locals_dict, locals_to_return=item.locals_to_return)
    return JSONResponse(content=result)

@app.post("/direct", dependencies=[Depends(get_api_key)])
async def direct(item: DirectExecution):
    print(item)
    f = globals().get(item.function_name, lambda *args,**kwargs: {"status": "error", "message": f"unkown function '{item.function_name}'"})
    result = f(**item.kwargs)
    return JSONResponse(content=result)

if __name__ == "__main__":
    import uvicorn
    print(f"Starting Carna Executor '{HOSTNAME}'...")
    print(f"Listening on: {LISTEN}:{PORT}")
    print("Press Ctrl+C to stop.")
    uvicorn.run(app, host=LISTEN, port=PORT)
