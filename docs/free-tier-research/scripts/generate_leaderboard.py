import os
from pathlib import Path
import subprocess

import requests
import pandas as pd
import numpy as np
import trueskill
import json

model_id_to_name = {}
model_id_to_org = {}
model_scores = {}

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_URL = "https://raw.githubusercontent.com/anomalyco/opencode/refs/heads/dev/packages/opencode/test/tool/fixtures/models-api.json"
TARGET_DIR = Path(os.path.join(BASE, "raw", "rankings"))
TARGET_DIR.mkdir(exist_ok=True)

try:
    with open(TARGET_DIR / "model_scores.json", "r") as f:
        model_scores = json.loads(f.read())
except:
    pass

def from_hf():
    DATA_URL = "https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset/resolve/main/text/latest-00000-of-00001.parquet"
    cache_file = TARGET_DIR / "lmsys-arena-latest.parquet"

    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    subprocess.run(["curl", "-sSL", DATA_URL, "-o", cache_file], check=True)

    df = pd.read_parquet(cache_file)

    df_overall = df[df['category'] == 'overall'].copy()
    df_overall = df_overall.sort_values('rating', ascending=False)

    models = []
    for _, row in df_overall.iterrows():
        model_id = row.get("model_name", "")
        for postfix in [" (xHigh)", "-xhigh", "-high", "-medium", " (thinking-minimal)", " (non-thinking)"]:
            if model_id.endswith(postfix):
                model_id = model_id[:-len(postfix)]
                break
        if model_id.endswith("-max") and not "qwen" in model_id:
            model_id = model_id[:-4]

        if row.get("organization"):
            model_id_to_org[model_id] = row.get("organization")

        benchmark_id = "hf_elo"       
        key = f"{model_id}\t{benchmark_id}"
        if not model_scores.get(key, None):
            model_scores[key] = []
        if not isinstance(model_scores[key], list):
            model_scores[key] = [model_scores[key], ]
        model_scores[key].append( float(row.get("rating", 0))   )

    if os.path.exists(cache_file):
        os.remove(cache_file)
    return models

def from_zeroeval():
    API_URL = "https://api.zeroeval.com/stats/v1/"
    API_KEY = "sk_ze_lNf97wkCzJC7uX5lBmYs3jy09M011RjbCHg5LZQgbyo"
    next_cursor = None
    dlcnt = 0
    for cat in ["code", "coding", "reasoning", "agents", "tool_calling"]:
        for i in range(100):
            url = API_URL + f"scores?category={cat}&limit=500"
            if next_cursor:
                url += f"&cursor={next_cursor}"
            response = requests.get(url, headers={"Authorization": f"Bearer {API_KEY}"})
            data = response.json()
            next_cursor = data.get("next_cursor", None)
            scores = data.get("scores", [])
            dlcnt += len(scores)
            for item in scores:
                model_id = item.get("model_id")
                model_name = item.get("model_name")
                model_id_to_name[model_id] = model_name
                model_id_to_org[model_id] = item.get("organization","")
                
                benchmark_id = item.get("benchmark_id")
                normalized_score = item.get("normalized_score")
                if not normalized_score:
                    continue
                key = f"{model_id}\t{benchmark_id}"
                if not model_scores.get(key, None):
                    model_scores[key] = []
                if not isinstance(model_scores[key], list):
                    model_scores[key] = [model_scores[key], ]
                model_scores[key].append(normalized_score)
            print(f"{dlcnt} scores received")
            if not next_cursor:
                break


def export_data():
    all_scores = []
    for key in model_scores.keys():
        model_id, benchmark_id = key.split("\t")
        if isinstance(model_scores[key], list):
            model_scores[key] = sum(model_scores[key]) / len(model_scores[key])
        all_scores.append([model_id, benchmark_id, model_scores[key] ])

    with open(TARGET_DIR / "model_scores.json", "w") as f:
        f.write(json.dumps(model_scores))
        
    # 1. Pull the data array using your existing function
    df = pd.DataFrame(all_scores, columns=["model_id", "benchmark_id", "normalized_score"])
    df = df.drop_duplicates(subset=["model_id", "benchmark_id", "normalized_score"])
   
    # Initialize TrueSkill Environment
    # We track unique benchmark contests sequentially. 
    env = trueskill.TrueSkill(mu=25.0, sigma=8.333, beta=4.167, tau=0.083, draw_probability=0.0)

    # Dictionary to hold the dynamic Rating objects for every model
    # Starts at default mu=25, sigma=8.333
    unique_models = df["model_id"].unique()
    ratings = {model_id: env.create_rating() for model_id in unique_models}

    # =====================================================================
    # THE MATCH SIMULATION LOOP
    # =====================================================================
    # We group by benchmark_id to treat each individual test as a separate game match
    grouped_benchmarks = df.groupby("benchmark_id")

    for benchmark_id, group in grouped_benchmarks:
        # Sort models within this benchmark by score descending (highest score wins)
        sorted_group = group.sort_values(by="normalized_score", ascending=False)
        
        # Exclude matches that don't have enough entries to form a meaningful contest
        if len(sorted_group) < 2:
            continue
            
        # TrueSkill expects a list of teams. In a Free-For-All competition, 
        # each team contains exactly one player model.
        teams = [[ratings[row["model_id"]]] for _, row in sorted_group.iterrows()]
        
        # Generate sequential game match rankings (e.g. 0th element gets 1st place, 1st gets 2nd place)
        # If scores are identical, you can assign them the same rank number to simulate a tie/draw
        match_ranks = list(range(len(sorted_group)))
        
        try:
            # Simulate match results and get updated rating adjustments
            updated_teams = env.rate(teams, ranks=match_ranks)
            
            # Save updated ratings back into our tracking registry
            for idx, (_, row) in enumerate(sorted_group.iterrows()):
                ratings[row["model_id"]] = updated_teams[idx][0]
                
        except ValueError as e:
            # Failsafe catch for any math convergence anomalies on massive ties
            continue

    # =====================================================================
    # COMPILE LEADERBOARD BY CONSERVATIVE RATING
    # =====================================================================
    leaderboard_records = []
    for model_id, rating in ratings.items():
        # Smart Formula: Conservative Score = mu - 3 * sigma
        conservative_score = round(rating.mu - (3 * rating.sigma),2)
        leaderboard_records.append({
            "Model ID": model_id,
            "Name" : model_id_to_name.get(model_id,""),
            "Organization" : model_id_to_org.get(model_id,""),
            "Score": conservative_score
        })
    leaderboard_records.sort(key=lambda x:x.get("Score"), reverse=True)

    with open( Path(TARGET_DIR, "leaderboard.csv"), "w") as f:
        f.write("Rank,Model ID,Name,Organization,Score\n")
        for index, leaderboard_record in enumerate(leaderboard_records):
            f.write(f'{index+1},{leaderboard_record["Model ID"]},{leaderboard_record["Name"]},{leaderboard_record["Organization"]},{leaderboard_record["Score"]}\n')

    print(f"Calculations complete! Saved true global rankings spreadsheet to: { Path(TARGET_DIR, "leaderboard.csv")}")

from_hf()
from_zeroeval()
export_data()