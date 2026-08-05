"""
Extract providers and model cards from awesome-free-llm-apis data.json.

Source: https://raw.githubusercontent.com/mnfst/awesome-free-llm-apis/refs/heads/main/data.json

Usage:
    python3 scripts/generate_from_awesome_apis.py          # use cached data
    python3 scripts/generate_from_awesome_apis.py --fetch  # re-fetch from URL

This script dynamically extracts everything from the JSON — no hardcoded
provider lists. Edit SKIP_PROVIDERS to exclude specific providers.
"""

import json, os, re, subprocess, sys, math, yaml

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_URL = "https://raw.githubusercontent.com/mnfst/awesome-free-llm-apis/refs/heads/main/data.json"
CACHE_FILE = os.path.join(BASE, "raw", "awesome-free-llm-apis.json")

# Skip these provider slugs (already exist or should not be created)
SKIP_PROVIDERS = {"google", "ollama"}

# Maps provider name from data.json → desired slug
SLUG_OVERRIDES = {
    "Google Gemini": "google",
    "Z AI (Zhipu AI)": "zhipu",
    "Mistral AI": "mistral",
    "AI21 Labs": "ai21",
    "Alibaba Cloud Model Studio": "alibaba",
    "Cloudflare Workers AI": "cloudflare-workers-ai",
    "GitHub Models": "github-models",
    "Hugging Face": "huggingface",
    "Kilo Code": "kilo",
    "NVIDIA NIM": "nvidia",
    "Ollama Cloud": "ollama-cloud",
    "OVHcloud AI Endpoints": "ovhcloud",
    "Aion Labs": "aion",
    "LLM7.io": "llm7",
}

def sanitize(s):
    s = s.lower().replace("(", "").replace(")", "").replace("'", "")
    s = re.sub(r'[^a-z0-9-]+', '-', s).strip('-')
    return s

def find_card(slug):
    """Find a model card by slug in the models directory (flat)."""
    models_dir = os.path.join(BASE, "raw", "models")
    fpath = os.path.join(models_dir, f"{slug}.md")
    if os.path.exists(fpath):
        return fpath
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


def parse_context(ctx_str):
    """Parse context string like '128K', '2M', '256K (8K on free)' → int."""
    if not ctx_str or ctx_str in ("—", "-", "Varies", "Up to 10M", 0):
        return 0
    if isinstance(ctx_str, (int, float)):
        return int(ctx_str)
    s = str(ctx_str).split("(")[0].split(" ")[0].strip()
    try:
        if s.endswith("M"):
            return int(float(s[:-1]) * 1000000)
        elif s.endswith("K"):
            return int(float(s[:-1]) * 1000)
        else:
            return int(s)
    except (ValueError, IndexError):
        return 0


def infer_from_modality(modality):
    """Infer vision/reasoning/tool_call flags from modality string."""
    mod = modality.lower() if modality else ""
    vision = any(kw in mod for kw in ["vision", "image", "video", "multimodal"])
    reasoning = "reasoning" in mod
    tool_call = not any(kw in mod for kw in ["reranking", "embedding", "embed", "audio to text",
                                              "speech-to-text", "image generation", "safety guard",
                                              "rerank"])
    return vision, reasoning, tool_call


def infer_family(slug):
    """Infer family from model slug."""
    bare = slug.lower()
    for p in STRIP_PREFIXES:
        if bare.startswith(p):
            bare = bare[len(p):]
            break
    bare = bare.strip("-")
    if bare.startswith("gpt"): return "gpt"
    if bare.startswith("qwen"): return "qwen"
    if bare.startswith("claude"): return "claude"
    if bare.startswith("llama"): return "llama"
    if bare.startswith("deepseek"): return "deepseek"
    if bare.startswith("gemini"): return "gemini"
    if bare.startswith("mistral"): return "mistral"
    if bare.startswith("nemotron"): return "nemotron"
    if bare.startswith("mixtral"): return "mixtral"
    if bare.startswith("phi"): return "phi"
    if bare.startswith("gemma"): return "gemma"
    if bare.startswith("yi"): return "yi"
    if bare.startswith("glm"): return "glm"
    if bare.startswith("command"): return "command"
    if bare.startswith("jamba"): return "jamba"
    if bare.startswith("dbrx"): return "dbrx"
    if bare.startswith("solar"): return "solar"
    if bare.startswith("groq"): return "groq"
    if bare.startswith("hermes"): return "hermes"
    if bare.startswith("dolphin"): return "dolphin"
    if bare.startswith("starling"): return "starling"
    if bare.startswith("zephyr"): return "zephyr"
    if bare.startswith("openchat"): return "openchat"
    if bare.startswith("neural-chat"): return "neural-chat"
    if bare.startswith("wizard"): return "wizard"
    if bare.startswith("vicuna"): return "vicuna"
    if bare.startswith("orca"): return "orca"
    if bare.startswith("falcon"): return "falcon"
    if bare.startswith("mpt"): return "mpt"
    if bare.startswith("redpajama"): return "redpajama"
    if bare.startswith("stablelm"): return "stablelm"
    if bare.startswith("xgen"): return "xgen"
    if bare.startswith("persimmon"): return "persimmon"
    if bare.startswith("cerebras"): return "cerebras"
    return "unknown"


def fetch_data():
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    subprocess.run(["curl", "-sSL", DATA_URL, "-o", CACHE_FILE], check=True)
    with open(CACHE_FILE) as f:
        return json.load(f)


def main():
    if "--fetch" in sys.argv:
        data = fetch_data()
    else:
        if not os.path.exists(CACHE_FILE):
            print("No cached data. Use --fetch to download.")
            data = fetch_data()
        else:
            with open(CACHE_FILE) as f:
                data = json.load(f)

    # Collect existing providers from providers/ directory
    existing = set()
    providers_dir = os.path.join(BASE, "raw", "providers")
    if os.path.exists(providers_dir):
        for d in os.listdir(providers_dir):
            if os.path.isdir(os.path.join(providers_dir, d)):
                if os.path.exists(os.path.join(providers_dir, d, "provider.md")):
                    existing.add(d)

    model_providers_map = {}  # model_slug → [provider_slug, ...]
    provider_info_list = []   # (slug, name, base_url, description, models_list)

    for p in data.get("providers", []):
        name = p["name"]
        slug = SLUG_OVERRIDES.get(name, sanitize(name))

        if slug in SKIP_PROVIDERS:
            continue

        base_url = p.get("baseUrl", "")
        description = p.get("description", f"{name} provides LLM API access.")

        # Group models (skip placeholder entries with null ids)
        model_entries = []
        for m in p.get("models", []):
            mid = m.get("id")
            if not mid:
                continue
            msanitized = sanitize(mid)
            model_entries.append((msanitized, mid, m))
            if msanitized not in model_providers_map:
                model_providers_map[msanitized] = []
            model_providers_map[msanitized].append(slug)

        provider_info_list.append((slug, name, base_url, description, model_entries))

    # Write provider files to providers/<slug>/provider.md
    for slug, name, base_url, description, model_entries in provider_info_list:
        pdir = os.path.join(BASE, "raw", "providers", slug)
        os.makedirs(pdir, exist_ok=True)

        # provider.md
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
        fm = {"name": name, "url": base_url, "self_hosted": False}
        fm.update(preserved)
        with open(md_path, "w") as f:
            f.write("---\n" + yaml.dump(fm, default_flow_style=False, allow_unicode=True).strip() + "\n---\n" + description + "\n")

        if slug not in existing:
            print(f"  NEW: {slug} ({name}) — {len(model_entries)} models")
        else:
            print(f"  UPD: {slug} ({name}) — {len(model_entries)} models")

    # Write/update model cards to models/<slug>.md (flat)
    new_cards = 0
    updated_cards = 0
    models_dir = os.path.join(BASE, "raw", "models")
    os.makedirs(models_dir, exist_ok=True)

    for slug, name, base_url, description, model_entries in provider_info_list:
        for msanitized, raw_id, mobj in model_entries:
            mfile = find_card(msanitized)

            # Parse metadata
            family = infer_family(msanitized)
            series = infer_series(msanitized)
            ctx = parse_context(mobj.get("context", ""))
            vision, reasoning, tool_call = infer_from_modality(mobj.get("modality", ""))

            if mfile:
                # Update existing: add this provider if not listed
                with open(mfile) as f:
                    content = f.read()
                if slug in content:
                    continue
                lines = content.split("\n")
                in_providers = False
                new_lines = []
                added = False
                for i, line in enumerate(lines):
                    new_lines.append(line)
                    if line.strip() == "providers:":
                        in_providers = True
                    elif in_providers and not line.strip().startswith("- "):
                        new_lines.insert(len(new_lines) - 1, f"  - {slug}")
                        in_providers = False
                        added = True
                if not added and in_providers:
                    new_lines.append(f"  - {slug}")
                with open(mfile, "w") as f:
                    f.write("\n".join(new_lines))
                updated_cards += 1
            else:
                # Create new model card in flat models/ directory
                mfile = os.path.join(models_dir, f"{msanitized}.md")
                with open(mfile, "w") as f:
                    f.write("---\n")
                    f.write(f"name: {msanitized}\n")
                    f.write(f"family: {family}\n")
                    f.write(f"series: {series}\n")
                    f.write(f"vision: {'true' if vision else 'false'}\n")
                    f.write(f"supports_reasoning: {'true' if reasoning else 'false'}\n")
                    f.write(f"supports_tool_call: {'true' if tool_call else 'false'}\n")
                    f.write(f"open_weights: false\n")
                    f.write(f"self_hosted: false\n")
                    if ctx > 0:
                        f.write(f"context_length: {ctx}\n")
                    f.write("providers:\n")
                    for ps in model_providers_map.get(msanitized, []):
                        f.write(f"  - {ps}\n")
                    f.write("---\n")
                    f.write(f"{mobj.get('name', mobj.get('id', msanitized))} from {name}.\n")
                new_cards += 1

    print(f"\nDone! Created/updated {len(provider_info_list)} providers")
    print(f"New model cards: {new_cards}, Updated: {updated_cards}")


if __name__ == "__main__":
    main()