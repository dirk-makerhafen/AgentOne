import os
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
from fastapi import FastAPI, Depends, HTTPException, status, Security
from executor.primitives import run_python_code, run_shell_script

import json
import sys

CONFIG_DEFAULTS = {
    "APIKEY": "my-api-key",
    "PORT": 8123,
    "LISTEN": "0.0.0.0",
    "NAME": "default-host"
}
CONFIG = {}

def load_all_config():
    """Loads default configuration and overrides with values from client_config.json."""
    global CONFIG
    CONFIG.update(CONFIG_DEFAULTS) 

    config_path = os.path.join(os.path.dirname(__file__), 'client_config.json')
    try:
        with open(config_path, 'r') as f:
            file_config = json.load(f)
            # Override defaults with values from client_config.json
            if 'client_api_key' in file_config:
                CONFIG["APIKEY"] = file_config['client_api_key']
            if 'client_port' in file_config:
                CONFIG["PORT"] = int(file_config['client_port'])
            if 'client_listen' in file_config:
                CONFIG["LISTEN"] = file_config['client_listen']
            if 'client_name' in file_config:
                CONFIG["NAME"] = file_config['client_name']
            
            print("Successfully loaded configuration from client_config.json.")
    except FileNotFoundError:
        print("Configuration file 'client_config.json' not found. Using default values.", file=sys.stderr)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error reading config from client_config.json: {e}. Using default values where possible.", file=sys.stderr)

    if not CONFIG.get("APIKEY"):
        print("\nFATAL: Executor API key is not configured.", file=sys.stderr)
        print("Please ensure a valid 'client_config.json' with a 'client_api_key' exists.", file=sys.stderr)
        sys.exit(1)
    
    return CONFIG.get("APIKEY")

API_KEY = load_all_config()

class ScriptExecution(BaseModel):
    source: str
    locals_dict: dict = {}
    locals_to_return: list = []

class ShellExecution(BaseModel):
    command: str
    env: dict[str, str] = {}
    timeout: int = 60

app = FastAPI(title=CONFIG["NAME"], description="A lightweight agent for remote python and shell execution.", version="1.0.0")

async def get_api_key(api_key: str = Security( APIKeyHeader(name="X-API-Key", auto_error=True))):
    if api_key == API_KEY:
        return api_key
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Could not validate credentials")

@app.get("/", dependencies=[Depends(get_api_key)])
async def root():
    return {"status": "ok", "name": CONFIG["NAME"], "port": CONFIG["PORT"], "listen": CONFIG["LISTEN"]}

@app.post("/shell", dependencies=[Depends(get_api_key)])
async def execute_shell_command(item: ShellExecution):
    result = run_shell_script(command=item.command, env=item.env, timeout=item.timeout)
    return JSONResponse(content=result)

@app.post("/python", dependencies=[Depends(get_api_key)])
async def execute_python_code(item: ScriptExecution):
    result = run_python_code(agentInstance=None, python_code_string = item.source, locals_dict=item.locals_dict, locals_to_return=item.locals_to_return)
    return JSONResponse(content=result)


if __name__ == "__main__":
    import uvicorn
    print(f"Starting executor '{CONFIG['NAME']}' on {CONFIG['LISTEN']}:{CONFIG['PORT']}...")
    uvicorn.run(app, host=CONFIG["LISTEN"], port=CONFIG["PORT"])
