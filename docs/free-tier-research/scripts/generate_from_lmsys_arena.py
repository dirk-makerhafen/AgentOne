"""
Extract model rankings from LMSYS Chatbot Arena leaderboard on Hugging Face.

Source: https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset

This dataset contains model Elo ratings from the Chatbot Arena, which is
a key benchmark for identifying flagship-tier models.

The data is in parquet format under the 'text' config, with 'overall' category
being the main leaderboard.

Usage:
    python3 scripts/generate_from_lmsys_arena.py          # use cached
    python3 scripts/generate_from_lmsys_arena.py --fetch  # re-fetch
"""

import json, os, re, subprocess, sys
from datetime import datetime, timezone

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_URL = "https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset/resolve/main/text/latest-00000-of-00001.parquet"
CACHE_FILE = os.path.join(BASE, "raw", "lmsys-arena-latest.parquet")

# Minimum Elo to consider "flagship" tier
FLAGSHIP_ELO_THRESHOLD = 1150

def fetch_data():
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    subprocess.run(["curl", "-sSL", DATA_URL, "-o", CACHE_FILE], check=True)

def parse_parquet():
    """Parse parquet and return list of models with Elo ratings from 'overall' category."""
    try:
        import pandas as pd
    except ImportError:
        print("ERROR: pandas required. Install with: pip install pandas pyarrow")
        return []

    df = pd.read_parquet(CACHE_FILE)
    # Filter to 'overall' category (main leaderboard)
    df_overall = df[df['category'] == 'overall'].copy()
    df_overall = df_overall.sort_values('rating', ascending=False)

    models = []
    for _, row in df_overall.iterrows():
        models.append({
            "name": row.get("model_name", ""),
            "elo": float(row.get("rating", 0)),
            "elo_lower": float(row.get("rating_lower", 0)),
            "elo_upper": float(row.get("rating_upper", 0)),
            "license": row.get("license", ""),
            "organization": row.get("organization", ""),
            "vote_count": int(row.get("vote_count", 0)),
            "rank": int(row.get("rank", 0)),
            "publish_date": str(row.get("leaderboard_publish_date", "")),
        })
    return models

def sanitize(s):
    s = s.lower().replace("(", "").replace(")", "").replace("'", "")
    s = re.sub(r'[^a-z0-9-]+', '-', s).strip('-')
    return s

def main():
    if "--fetch" in sys.argv:
        fetch_data()
    elif not os.path.exists(CACHE_FILE):
        print("No cached data. Use --fetch to download.")
        fetch_data()

    models = parse_parquet()
    print(f"  Parsed {len(models)} models from LMSYS Arena leaderboard (overall category)")

    # Filter to flagship tier
    flagship = [m for m in models if m["elo"] >= FLAGSHIP_ELO_THRESHOLD]

    print(f"\n  Flagship models (Elo >= {FLAGSHIP_ELO_THRESHOLD}):")
    for m in flagship[:30]:
        print(f"    {m['name']:50s} Elo: {m['elo']:.1f}  ({m['organization']}, {m['license']})")

    # Write summary to raw/ for reference during curation
    summary_file = os.path.join(BASE, "raw", "lmsys-flagship-summary.json")
    with open(summary_file, "w") as f:
        json.dump({
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "threshold": FLAGSHIP_ELO_THRESHOLD,
            "total_models": len(models),
            "flagship_models": flagship,
        }, f, indent=2)
    print(f"\n  Summary written to {summary_file}")

    # Print top models for quick reference
    print("\n  Top flagship models to consider for curation:")
    for i, m in enumerate(flagship[:15], 1):
        print(f"    {i:2d}. {m['name']} (Elo: {m['elo']:.1f}) - {m['organization']} [{m['license']}]")

    # Also identify open-weight flagship models
    open_weight = [m for m in flagship if m["license"] != "Proprietary"]
    if open_weight:
        print("\n  Open-weight flagship models:")
        for m in open_weight[:10]:
            print(f"    - {m['name']} (Elo: {m['elo']:.1f}) - {m['organization']} [{m['license']}]")

if __name__ == "__main__":
    main()