"""
Extract provider metadata from the awesome-free-llm-apis skill references.

Sources:
  - https://github.com/mnfst/awesome-free-llm-apis/blob/main/free-llm-apis/references/provider-apis.md
  - https://github.com/mnfst/awesome-free-llm-apis/blob/main/free-llm-apis/references/inference-providers.md

Pulls provider names, model lists, API base URLs, rate limits, and env var names
from the SKILL.md reference files.

Usage:
    python3 scripts/generate_from_awesome_repo.py          # use cached
    python3 scripts/generate_from_awesome_repo.py --fetch  # re-fetch
"""

import json, os, re, subprocess, sys, yaml

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_DIR = os.path.join(BASE, "raw", "awesome-repo-cache")
os.makedirs(CACHE_DIR, exist_ok=True)

REF_URLS = {
    "provider-apis": "https://raw.githubusercontent.com/mnfst/awesome-free-llm-apis/main/free-llm-apis/references/provider-apis.md",
    "inference-providers": "https://raw.githubusercontent.com/mnfst/awesome-free-llm-apis/main/free-llm-apis/references/inference-providers.md",
}

# Maps provider display names from the reference docs → existing provider slug
# when sanitize(name) doesn't match the existing directory name.
SLUG_MERGE_MAP = {
    "Google Gemini": "google",
    "Mistral AI": "mistral",
    "Zhipu AI": "zhipu",
    "Hugging Face": "huggingface",
    "NVIDIA NIM": "nvidia",
    "LLM7.io": "llm7",
}

# ── Curated free-credit map (same as enrich_free_info.py) ─────────────
FREE_CREDIT_MAP = {
    "google": {"free_credit": "$300 credit for new users", "requires_credit_card": True},
    "together": {"free_credit": "$1 credit on signup", "requires_credit_card": True},
    "deepinfra": {"free_credit": "$5 credit on signup", "requires_credit_card": True},
    "nebius": {"free_credit": "$1 free signup credits", "requires_credit_card": False},
    "nscale": {"free_credit": "$5 free signup credits", "requires_credit_card": False},
    "xai": {"free_credit": "$25 sign-up credit (one-time; additional $150/month via opt-in data-sharing)", "requires_credit_card": False},
    "alibaba": {"free_credit": "1M free tokens per Qwen model on signup (expires 90 days)", "requires_credit_card": False},
    "deepseek": {"free_credit": "5M free tokens on signup (expires 30 days)", "requires_credit_card": False},
    "ai21": {"free_credit": "$10 trial credits at signup (expires 3 months)", "requires_credit_card": False},
    "cohere": {"free_credit": "1,000 API calls/month on Trial plan", "requires_credit_card": False},
    "huggingface": {"free_credit": "$0.10/month in free Inference Provider credits", "requires_credit_card": False},
    "cloudflare-workers-ai": {"free_credit": "10,000 Neurons/day free", "requires_credit_card": False},
    "cerebras": {"free_credit": "1M tokens/day free tier", "requires_credit_card": False},
    "mistral": {"free_credit": "~1B tokens/month free (Experiment plan)", "requires_credit_card": False},
    "groq": {"free_credit": "Free tier (no credit card)", "requires_credit_card": False},
    "github-models": {"free_credit": "Free for prototyping (GitHub users)", "requires_credit_card": False},
    "siliconflow": {"free_credit": "3 permanently free models; free tier capped at 50 req/day", "requires_credit_card": False},
    "zhipu": {"free_credit": "Permanent free models", "requires_credit_card": False},
    "ovhcloud": {"free_credit": "Free anonymous tier (no API key, no signup)", "requires_credit_card": False},
    "nvidia": {"free_credit": "Free with NVIDIA Developer Program", "requires_credit_card": True},
    "modelscope": {"free_credit": "Free API-Inference (requires Alibaba Cloud account)", "requires_credit_card": False},
    "ollama-cloud": {"free_credit": "Free tier with qualitative usage limits", "requires_credit_card": False},
    "kilo": {"free_credit": "Free models with no credit card required", "requires_credit_card": False},
    "openrouter": {"free_credit": "~28 free models (marked with :free suffix)", "requires_credit_card": False},
    "novita": {"free_credit": "Free tier with rate limits", "requires_credit_card": False},
}


def sanitize(s):
    s = s.lower().replace("(", "").replace(")", "").replace("'", "")
    s = re.sub(r'[^a-z0-9-]+', '-', s).strip('-')
    return s


def parse_yaml_frontmatter(path):
    """Return (dict, body_str) from a --- delimited file."""
    with open(path) as f:
        content = f.read()
    m = re.match(r'^---\n(.+?)\n---\n?(.*)', content, re.DOTALL)
    if not m:
        return {}, content
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except Exception:
        data = {}
    return data, m.group(2)


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


def fetch_all():
    for name, url in REF_URLS.items():
        dest = os.path.join(CACHE_DIR, f"{name}.md")
        subprocess.run(["curl", "-sSL", url, "-o", dest], check=True)
        print(f"  Fetched {name}.md")

def parse_provider_section(lines, start):
    """Parse a provider section starting at line `start` (the ## heading line)."""
    heading = lines[start]
    name = heading.lstrip("#").strip()

    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## ") and i > start + 1:
            end = i
            break
        if lines[i].startswith("---") and i > start + 1:
            end = i
            break

    section = "\n".join(lines[start+1:end])

    models_match = re.search(r'\*\*Models:\*\*\s*(.+)', section)
    models_str = models_match.group(1) if models_match else ""

    limits_match = re.search(r'\*\*Limits:\*\*\s*(.+)', section)
    limits = limits_match.group(1).strip() if limits_match else ""

    # Extract base_url from code examples (between quotes in base_url=...)
    url_match = re.search(r'base_url\s*=\s*["\']([^"\']+)["\']', section)
    base_url = url_match.group(1) if url_match else ""

    # Extract env vars
    env_match = re.search(r'export\s+(\w+)="', section)
    env_var = env_match.group(1) if env_match else ""

    # Parse model list (comma-separated, may include +N more)
    models = []
    for m in re.split(r',\s*', models_str):
        m = m.strip()
        if not m:
            continue
        if re.match(r'^\+?\d+', m):
            continue
        if "more" in m.lower():
            continue
        models.append(m)

    return {
        "name": name,
        "slug": sanitize(name),
        "models": models,
        "base_url": base_url,
        "limits": limits,
        "env_var": env_var,
    }

def parse_reference(content):
    """Parse a reference markdown file into a list of provider dicts."""
    lines = content.split("\n")
    providers = []
    for i, line in enumerate(lines):
        if line.startswith("## ") and not line.startswith("### "):
            provider = parse_provider_section(lines, i)
            if provider["name"] and provider["name"] != "Provider APIs - Setup Guides" and provider["name"] != "Inference Providers - Setup Guides":
                providers.append(provider)
    return providers

def main():
    if "--fetch" in sys.argv:
        fetch_all()

    all_providers = []
    for name in REF_URLS:
        fpath = os.path.join(CACHE_DIR, f"{name}.md")
        if not os.path.exists(fpath):
            print(f"No cache for {name}. Use --fetch first.")
            fetch_all()
        with open(fpath) as f:
            content = f.read()
        providers = parse_reference(content)
        all_providers.extend(providers)
        print(f"  Parsed {len(providers)} providers from {name}.md")

    # Load existing provider dirs from providers/
    existing = set()
    providers_dir = os.path.join(BASE, "raw", "providers")
    if os.path.exists(providers_dir):
        for d in os.listdir(providers_dir):
            if os.path.isdir(os.path.join(providers_dir, d)):
                if os.path.exists(os.path.join(providers_dir, d, "provider.md")):
                    existing.add(d)

    updated_providers = 0
    updated_cards = 0
    skipped = 0

    for p in all_providers:
        slug = SLUG_MERGE_MAP.get(p["name"], p["slug"])
        if slug == "":
            skipped += 1
            continue

        pdir = os.path.join(BASE, "raw", "providers", slug)
        is_new = slug not in existing
        if is_new:
            os.makedirs(pdir, exist_ok=True)

        # Update or create provider.md — enhance with URL, limits, env var, free tier
        md_path = os.path.join(pdir, "provider.md")
        if os.path.exists(md_path):
            data, desc = parse_yaml_frontmatter(md_path)
        else:
            data = {"name": p["name"], "url": "", "self_hosted": False}
            desc = ""

        existing_url = data.get("url", "")

        # Merge URL from this source if more specific
        new_url = existing_url or p["base_url"]
        if p["base_url"] and p["base_url"] != existing_url and not existing_url:
            new_url = p["base_url"]
        data["url"] = new_url
        if not data.get("name"):
            data["name"] = p["name"]

        # Write free-tier info to structured frontmatter
        if p["limits"]:
            data["free_tier"] = True
            if not data.get("free_tier_description"):
                data["free_tier_description"] = p["limits"]

        # Apply curated credit map (don't override existing)
        if slug in FREE_CREDIT_MAP:
            for k, v in FREE_CREDIT_MAP[slug].items():
                if k not in data:
                    data[k] = v

        # Build enhanced description (env var, base URL — but NOT limits anymore)
        extra = []
        if p["env_var"]:
            extra.append(f"Auth via {p['env_var']} env var")
        if p["base_url"] and not existing_url:
            extra.append(f"API base: {p['base_url']}")
        enhanced_desc = desc
        if extra:
            enhanced_desc = desc.rstrip(".") + ". " + ". ".join(extra) + "." if desc else ". ".join(extra) + "."

        # Write frontmatter + description
        with open(md_path, "w") as f:
            f.write("---\n")
            f.write(yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False).rstrip())
            f.write("\n---\n")
            if enhanced_desc:
                f.write(enhanced_desc.strip() + "\n")

        # Update model cards — add this provider to matching model cards
        for model_name in p["models"]:
            mslug = sanitize(model_name)
            mfile = find_card(mslug)
            if mfile:
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

        if is_new:
            print(f"  NEW: {slug} ({p['name']}) — {len(p['models'])} models ref")
        else:
            updated_providers += 1

    print(f"\nDone! Updated {updated_providers} providers, {updated_cards} model cards linked ({skipped} skipped)")

if __name__ == "__main__":
    main()