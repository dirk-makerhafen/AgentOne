"""
Enhance model card names using MODEL_TO_NAME_MAPPING from free-llm-api-resources.

Source: https://github.com/cheahjs/free-llm-api-resources/blob/main/src/data.py

Parses the MODEL_TO_NAME_MAPPING dict and applies human-readable names to
matching model cards. Ignores entries matching SKIP_PATTERNS.

Usage:
    python3 scripts/generate_from_free_api_resources.py          # use cached
    python3 scripts/generate_from_free_api_resources.py --fetch  # re-fetch
"""

import ast, os, re, subprocess, sys

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_URL = "https://raw.githubusercontent.com/cheahjs/free-llm-api-resources/refs/heads/main/src/data.py"
CACHE_FILE = os.path.join(BASE, "raw", "free-api-resources-data.py")

SKIP_PATTERNS = re.compile(
    r'(HF_MIRROR|FLUX\.|StableDiffusion|TTS|test|SDXL|Monad)', re.I
)

def sanitize(s):
    s = re.sub(r'[^a-z0-9-]', '-', s.lower().replace(':', '-').replace('/', '-').replace('_', '-').replace('.', '-').replace(' ', '-'))
    return s.strip('-')

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


def fetch():
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    subprocess.run(["curl", "-sSL", DATA_URL, "-o", CACHE_FILE], check=True)

def parse_mapping():
    with open(CACHE_FILE) as f:
        content = f.read()

    # Extract MODEL_TO_NAME_MAPPING dict
    start = content.find("MODEL_TO_NAME_MAPPING")
    if start == -1:
        print("ERROR: MODEL_TO_NAME_MAPPING not found in fetched data")
        return {}

    brace = content.find("{", start)
    if brace == -1:
        return {}

    # We need to find the matching closing brace. Use ast to parse the dict literal.
    # Find the substring that looks like a dict literal.
    # Walk backwards from brace to find the end of the line, then extract.
    dict_str = content[brace:]
    try:
        parsed = ast.literal_eval(dict_str)
    except (ValueError, SyntaxError):
        # Try to find the matching dict by counting braces
        depth = 0
        end = 0
        for i, ch in enumerate(dict_str):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end == 0:
            print("ERROR: Could not find closing brace of MODEL_TO_NAME_MAPPING")
            return {}
        try:
            parsed = ast.literal_eval(dict_str[:end])
        except (ValueError, SyntaxError) as e:
            print(f"ERROR: Failed to parse dict: {e}")
            return {}

    if not isinstance(parsed, dict):
        return {}
    return parsed

def main():
    if "--fetch" in sys.argv:
        fetch()
    elif not os.path.exists(CACHE_FILE):
        print("No cached data. Use --fetch to download.")
        fetch()

    mapping = parse_mapping()
    if not mapping:
        print("No mapping parsed. Aborting.")
        return

    print(f"  Parsed {len(mapping)} entries from MODEL_TO_NAME_MAPPING")

    models_dir = os.path.join(BASE, "raw", "models")
    if not os.path.exists(models_dir):
        print(f"ERROR: {models_dir} does not exist")
        return

    updated = 0
    skipped_models = 0
    new_cards = 0

    for raw_id, human_name in sorted(mapping.items()):
        if SKIP_PATTERNS.search(human_name) or SKIP_PATTERNS.search(raw_id):
            skipped_models += 1
            continue

        mslug = sanitize(raw_id)
        mfile = find_card(mslug)

        if not mfile:
            # Create minimal card in flat models/ directory
            family = infer_family(mslug)
            series = infer_series(mslug)
            mfile = os.path.join(models_dir, f"{mslug}.md")
            with open(mfile, "w") as f:
                f.write(f"---\nname: {mslug}\nfamily: {family}\nseries: {series}\nvision: false\n")
                f.write("supports_reasoning: false\nsupports_tool_call: false\n")
                f.write("open_weights: false\nself_hosted: false\nproviders: []\n")
                f.write(f"---\n{human_name}\n")
            new_cards += 1
            print(f"  NEW: {mslug} ← {human_name}")
            continue

        # Read existing card, update description if better name available
        with open(mfile) as f:
            content = f.read()

        # Check if the card already has a good description
        body_start = content.rfind("---\n")
        if body_start != -1:
            body = content[body_start + 4:].strip()
            # Only update if current body is just a slug or auto-generated text
            if body == mslug or not body or len(body) < 3:
                parts = content.split("---")
                frontmatter = parts[1]
                rest = parts[2] if len(parts) > 2 else ""
                new_content = f"---{frontmatter}---{human_name}\n"
                with open(mfile, "w") as f:
                    f.write(new_content)
                updated += 1
                continue

        # Even if body is fine, add the raw_id as an alias if not present
        if "aliases:" not in content and raw_id != mslug:
            lines = content.split("\n")
            # Insert after providers line or at end of frontmatter
            in_providers = False
            new_lines = []
            inserted = False
            for i, line in enumerate(lines):
                new_lines.append(line)
                if line.strip() == "providers:":
                    in_providers = True
                elif in_providers and not line.strip().startswith("- ") and not inserted:
                    new_lines.insert(len(new_lines) - 1, f"aliases:\n  - \"{raw_id}\"")
                    in_providers = False
                    inserted = True
                elif i == len(lines) - 2 and not inserted:
                    # Last line before closing ---
                    new_lines.insert(len(new_lines) - 1, f"  aliases:\n    - \"{raw_id}\"")
                    inserted = True
            if inserted:
                with open(mfile, "w") as f:
                    f.write("\n".join(new_lines))
                updated += 1

    print(f"\nDone! Updated {updated} cards, created {new_cards} new, skipped {skipped_models}")

if __name__ == "__main__":
    main()