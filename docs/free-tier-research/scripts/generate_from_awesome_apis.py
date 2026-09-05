"""

Source: https://raw.githubusercontent.com/mnfst/awesome-free-llm-apis/refs/heads/main/data.json

Usage:
    python3 scripts/generate_from_awesome_apis.py 

Creates  "raw/awesome-free-llm-apis/" folder with <providername>.json files
"""

from pathlib import Path

import requests
import json, os

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_URL = "https://raw.githubusercontent.com/mnfst/awesome-free-llm-apis/refs/heads/main/data.json"
TARGET_DIR = os.path.join(BASE, "raw", "awesome-free-llm-apis/")

def main():
    resp = requests.get(DATA_URL, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    Path(TARGET_DIR).mkdir(exist_ok=True, parents=True)
    for provider in payload["providers"]:
        path = Path(TARGET_DIR, provider.get("name") + ".json")
        with open(path,"w") as f:
            f.write(json.dumps(provider, indent=2))
            print(f"created/updated '{path}'")

if __name__ == "__main__":
    main()