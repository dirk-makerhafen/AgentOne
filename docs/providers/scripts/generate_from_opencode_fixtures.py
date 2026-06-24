"""
Generate provider directories and model cards from
https://raw.githubusercontent.com/anomalyco/opencode/refs/heads/dev/packages/opencode/test/tool/fixtures/models-api.json

Usage:  python3 scripts/generate_from_opencode_fixtures.py
        python3 scripts/generate_from_opencode_fixtures.py --fetch

Edit SKIP_IDS below to control which providers to skip.
"""

import json, os, re, subprocess, sys, yaml

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_URL = "https://raw.githubusercontent.com/anomalyco/opencode/refs/heads/dev/packages/opencode/test/tool/fixtures/models-api.json"
DATA_FILE = "/tmp/opencode-models-api.json"

SKIP_IDS = {
    "alibaba-cn", "alibaba-coding-plan", "alibaba-coding-plan-cn",
    "moonshotai-cn", "minimax-cn", "minimax-cn-coding-plan", "minimax-coding-plan",
    "siliconflow-cn",
    "xiaomi-token-plan-cn", "xiaomi-token-plan-sgp", "xiaomi-token-plan-ams",
    "tencent-coding-plan", "tencent-tokenhub", "kuae-cloud-coding-plan",
    "kimi-for-coding", "zai-coding-plan", "zhipuai-coding-plan",
    "github-copilot", "gitlab", "frogbot", "v0",
    "amazon-bedrock", "azure", "azure-cognitive-services",
    "digitalocean", "vultr", "google-vertex", "google-vertex-anthropic",
    "abliteration-ai", "wafer.ai", "privatemode-ai", "stackit",
    "bailing", "drun", "iflowcn", "jiekou", "qihang-ai", "qiniu-ai",
    "opencode", "opencode-go", "moark", "scaleway",
}

def sanitize(s):
    return re.sub(r'[^a-z0-9-]', '', s.lower().replace(':', '-').replace('/', '-').replace('_', '-').replace('.', '-').replace(' ', '-'))

def find_card(slug):
    """Find a model card by slug in the models directory (recursive)."""
    models_dir = os.path.join(BASE, "models")
    for root, dirs, files in os.walk(models_dir):
        for fname in files:
            if fname == f"{slug}.md":
                return os.path.join(root, fname)
    return None

STRIP_PREFIXES = sorted([
    "accounts-fireworks-models-", "alibaba-", "anthropic--", "anthropic-",
    "cf-", "cohere-", "databricks-", "deepseek-ai-", "google-",
    "hf-", "meta-llama-", "microsoft-", "mistralai-", "mistral-",
    "moonshotai-", "nvidia-", "openai-", "workers-ai-cf-", "workers-ai-",
    "x-ai-", "xai-",
], key=len, reverse=True)

def infer_series(slug):
    bare = slug.lower()
    for p in STRIP_PREFIXES:
        if bare.startswith(p):
            bare = bare[len(p):]
            break
    bare = bare.strip("-")
    # GPT series
    m = re.match(r'^(gpt-\d+(?:\.\d+)?[a-z]*)', bare)
    if m: return m.group(1)
    # Qwen series
    m = re.match(r'^(qwen[\d.]*[\w]*)', bare)
    if m: return m.group(1).rstrip("-").replace("3p6","3.6").replace("2p5","2.5")
    # Claude series
    m = re.match(r'^(claude-\d+(?:-\d+)?(?:-\w+)?)', bare)
    if m: return m.group(1)
    # Llama series
    if bare.startswith("llama-"):
        rest = bare[6:]
        vm = re.match(r'^(\d+(?:\.\d+)?)', rest)
        if vm:
            v = vm.group(1)
            rem = rest[vm.end():]
            sm = re.match(r'^-(\d+)(?!\d)(?![bBeE])', rem)
            if sm: v += f"-{sm.group(1)}"
            return f"llama-{v}"
    # DeepSeek series
    if bare.startswith("deepseek-"): return "-".join(bare.split("-")[:2])
    # Gemini series
    m = re.match(r'^(gemini-\d+(?:\.\d+)?(?:-\w+)?)', bare)
    if m: return m.group(1)
    # Fallback: first 2 segments
    parts = bare.split("-")
    if len(parts) >= 2: return f"{parts[0]}-{parts[1]}"
    return bare


def fetch_data():
    subprocess.run(["curl", "-sSL", DATA_URL, "-o", DATA_FILE], check=True)
    with open(DATA_FILE) as f:
        return json.load(f)

def main():
    if "--fetch" in sys.argv:
        data = fetch_data()
    else:
        with open(DATA_FILE) as f:
            data = json.load(f)

    existing_providers = set()
    for d in os.listdir(BASE):
        if os.path.isdir(os.path.join(BASE, d)) and d not in ("models", "scripts") and not d.startswith("."):
            if os.path.exists(os.path.join(BASE, d, "provider.md")):
                existing_providers.add(d)

    for pid, info in sorted(data.items()):
        if pid in existing_providers:
            continue
        if pid in SKIP_IDS:
            continue
        if not info.get("models"):
            continue

        pdir = os.path.join(BASE, pid)
        os.makedirs(pdir, exist_ok=True)

        pname = info.get("name", pid)
        purl = info.get("api", "")
        env_keys = info.get("env", [])
        pdesc = f"{pname} provides {len(info['models'])} AI models"
        if env_keys:
            pdesc += f" (auth: {', '.join(env_keys)})"
        pdesc += "."

        md_path = os.path.join(pdir, "provider.md")
        preserved = {}
        if os.path.exists(md_path):
            with open(md_path) as f:
                content = f.read()
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    try:
                        existing = yaml.safe_load(parts[1])
                        if isinstance(existing, dict):
                            for key in ("free_tier", "free_tier_description", "free_credit", "requires_credit_card"):
                                if key in existing:
                                    preserved[key] = existing[key]
                    except Exception:
                        pass
        fm = {"name": pname, "url": purl, "self_hosted": False}
        fm.update(preserved)
        with open(md_path, "w") as f:
            f.write("---\n" + yaml.dump(fm, default_flow_style=False, allow_unicode=True).strip() + "\n---\n" + pdesc + "\n")

        with open(os.path.join(pdir, "models.md"), "w") as f:
            f.write("---\nmodels:\n")
            for mid, _ in sorted(info["models"].items()):
                mslug = sanitize(mid)
                if mslug != sanitize(mid):
                    f.write(f"  - name: {mslug}\n    model_name: {mid}\n")
                else:
                    f.write(f"  - name: {mslug}\n")
            f.write("---\n")

        print(f"  Created {pid} ({pname})")

    # Update existing model cards with new provider references
    for pid, info in sorted(data.items()):
        if pid in SKIP_IDS:
            continue
        if not os.path.exists(os.path.join(BASE, pid, "provider.md")):
            continue
        for mid, minfo in info.get("models", {}).items():
            mslug = sanitize(mid)
            mfile = find_card(mslug)
            if not mfile:
                # Create basic model card in family subdirectory
                family = minfo.get("family", "unknown") or "unknown"
                series = infer_series(mslug)
                models_dir = os.path.join(BASE, "models")
                fam_dir = os.path.join(models_dir, family, series)
                os.makedirs(fam_dir, exist_ok=True)
                mfile = os.path.join(fam_dir, f"{mslug}.md")
                inp_mods = minfo.get("modalities", {}).get("input", []) if isinstance(minfo.get("modalities"), dict) else []
                vision = "image" in inp_mods or "video" in inp_mods
                ctx = minfo.get("limit", {}).get("context", 0)
                with open(mfile, "w") as f:
                    f.write("---\n")
                    f.write(f"name: {mslug}\nfamily: {family}\nseries: {series}\n")
                    f.write(f"vision: {'true' if vision else 'false'}\n")
                    f.write(f"supports_reasoning: {'true' if minfo.get('reasoning') else 'false'}\n")
                    f.write(f"supports_tool_call: {'true' if minfo.get('tool_call') else 'false'}\n")
                    f.write(f"open_weights: {'true' if minfo.get('open_weights') else 'false'}\n")
                    f.write("self_hosted: false\n")
                    if ctx and ctx > 0:
                        f.write(f"context_length: {ctx}\n")
                    f.write("providers:\n")
                    # Find all providers serving this model
                    for pid2, info2 in sorted(data.items()):
                        if pid2 in SKIP_IDS:
                            continue
                        if not os.path.exists(os.path.join(BASE, pid2, "provider.md")):
                            continue
                        if mid in info2.get("models", {}):
                            f.write(f"  - {pid2}\n")
                    f.write("---\n")
                    f.write(f"{minfo.get('name', mslug)} served by {pid}.\n")
            else:
                # Update existing: add this provider if not already listed
                with open(mfile) as f:
                    content = f.read()
                if pid not in content:
                    lines = content.split("\n")
                    in_providers = False
                    new_lines = []
                    added = False
                    for i, line in enumerate(lines):
                        new_lines.append(line)
                        if line.strip() == "providers:":
                            in_providers = True
                        elif in_providers and not line.strip().startswith("- "):
                            new_lines.insert(len(new_lines)-1, f"  - {pid}")
                            in_providers = False
                            added = True
                    if not added and in_providers:
                        new_lines.append(f"  - {pid}")
                    with open(mfile, "w") as f:
                        f.write("\n".join(new_lines))

    print(f"\nDone!")

if __name__ == "__main__":
    main()
