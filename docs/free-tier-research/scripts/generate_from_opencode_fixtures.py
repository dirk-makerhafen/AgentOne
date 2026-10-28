"""
Generate provider directories and model cards from Opencode sources.

Two data sources:
1. Live API: https://opencode.ai/zen/v1/models - current model list (used for discovering free models)
2. Fixture: https://raw.githubusercontent.com/anomalyco/opencode/2.0/packages/opencode/test/tool/fixtures/models-api.json - detailed model metadata (stale, last updated ~April 2026)

Usage:  python3 scripts/generate_from_opencode_fixtures.py
Creates  "raw/opencode-models-api/" directory structure / json files with provider and model information.
"""

from pathlib import Path

import requests
import json, os

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURE_URL = "https://raw.githubusercontent.com/anomalyco/opencode/2.0/packages/opencode/test/tool/fixtures/models-api.json"
LIVE_API_URL = "https://opencode.ai/zen/v1/models"
TARGET_DIR = os.path.join(BASE, "raw", "opencode-models-api")

def fetch_live_model_ids():
    """Fetch current model IDs from the live Opencode Zen API."""
    resp = requests.get(LIVE_API_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return [model["id"] for model in data.get("data", [])]

def fetch_fixture_data():
    """Fetch detailed provider/model data from the GitHub fixture."""
    resp = requests.get(FIXTURE_URL, timeout=30)
    resp.raise_for_status()
    return resp.json()

def main():
    # Fetch live model IDs to know what's currently available
    live_model_ids = set(fetch_live_model_ids())
    print(f"Live API reports {len(live_model_ids)} models for opencode provider")
    
    # Fetch detailed fixture data
    fixture_data = fetch_fixture_data()
    
    Path(TARGET_DIR).mkdir(exist_ok=True, parents=True)
    
    for key, provider in fixture_data.items():
        path = Path(TARGET_DIR, key)
        path.mkdir(exist_ok=True)
        file = path / f"{key}.json"
        
        models = provider.get("models", {})
        # Filter models to only those currently in live API (for opencode provider)
        if key == "opencode":
            original_count = len(models)
            models = {k: v for k, v in models.items() if k in live_model_ids}
            filtered_count = len(models)
            if original_count != filtered_count:
                print(f"  Filtered opencode models: {original_count} -> {filtered_count} (live API has {len(live_model_ids)})")
        
        with open(file, "w") as f:
            provider_copy = {k: v for k, v in provider.items() if k != "models"}
            f.write(json.dumps(provider_copy, indent=2))
            print(f"created/updated '{path}'")
            for model_id, model in models.items():
                model_id_safe = model_id.split("/")[-1]
                mfile = path / f"model_{model_id_safe}.json"
                with open(mfile, "w") as f1:
                    f1.write(json.dumps(model, indent=2))
            print(f"created/updated {len(models)} models")
    
    # Also save the live model list for reference
    live_file = Path(TARGET_DIR) / "opencode" / "live_model_list.json"
    live_file.parent.mkdir(exist_ok=True)
    with open(live_file, "w") as f:
        f.write(json.dumps({"model_ids": sorted(live_model_ids), "count": len(live_model_ids), "source": LIVE_API_URL}, indent=2))
    print(f"created/updated live model list at '{live_file}'")
    
    return

if __name__ == "__main__":
    main()