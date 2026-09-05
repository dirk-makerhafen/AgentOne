"""
Generate provider directories and model cards from
https://raw.githubusercontent.com/anomalyco/opencode/refs/heads/dev/packages/opencode/test/tool/fixtures/models-api.json

Usage:  python3 scripts/generate_from_opencode_fixtures.py
Creates  "raw/opencode-models-api/" directory structure / json files with many information about providers and models, taken from the large and public opencode project

"""

from pathlib import Path

import requests
import json, os

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_URL = "https://raw.githubusercontent.com/anomalyco/opencode/refs/heads/dev/packages/opencode/test/tool/fixtures/models-api.json"
TARGET_DIR = os.path.join(BASE, "raw", "opencode-models-api")

def main():
    resp = requests.get(DATA_URL, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    Path(TARGET_DIR).mkdir(exist_ok=True, parents=True)
    for key, provider in payload.items():
        path = Path(TARGET_DIR, key )
        path.mkdir(exist_ok=True)
        file = path / f"{key}.json"
        with open(file,"w") as f:
            models = provider["models"]
            del provider["models"]
            f.write(json.dumps(provider, indent=2))
            print(f"created/updated '{path}'")
            for model_id, model in models.items():
                model_id = model_id.split("/")[-1]
                mfile = path / f"model_{model_id}.json"
                with open(mfile,"w") as f1:
                    f1.write(json.dumps(model, indent=2))
            print(f"created/updated {len(models.items())} models")
    return

if __name__ == "__main__":
    main()