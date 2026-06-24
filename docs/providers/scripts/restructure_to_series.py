"""
Restructure model cards into models/<family>/<series>/<slug>.md hierarchy.

Introduces a `series` frontmatter field to capture the model series variant
(e.g., gpt-4o, qwen3, claude-3.5-sonnet). Consolidates granular families
into broader ones (e.g., claude-{sonnet,opus,haiku} → claude).

Usage:
    python3 scripts/restructure_to_series.py          # dry-run (show changes)
    python3 scripts/restructure_to_series.py --apply   # perform restructuring
"""

import os, re, sys, yaml
from collections import defaultdict

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(BASE, "models")

# ── Family consolidation ──────────────────────────────────────────────
# Current sub-family → broad family mapping
FAMILY_MERGE_MAP = {
    "claude": "claude",
    "claude-haiku": "claude",
    "claude-opus": "claude",
    "claude-sonnet": "claude",
    "gemini": "gemini",
    "gemini-embedding": "gemini",
    "gemini-flash": "gemini",
    "gemini-flash-lite": "gemini",
    "gemini-pro": "gemini",
    "deepseek": "deepseek",
    "deepseek-flash": "deepseek",
    "deepseek-thinking": "deepseek",
    "mistral": "mistral",
    "mistral-embed": "mistral",
    "mistral-large": "mistral",
    "mistral-medium": "mistral",
    "mistral-nemo": "mistral",
    "mistral-small": "mistral",
    "mixtral": "mistral",
    "ministral": "mistral",
    "ministral-3": "mistral",
    "magistral-medium": "mistral",
    "magistral-small": "mistral",
    "codestral": "mistral",
    "codestral-embed": "mistral",
    "voxtral": "mistral",
    "pixtral": "mistral",
    "gpt": "gpt",
    "gpt-codex": "gpt",
    "gpt-codex-mini": "gpt",
    "gpt-codex-spark": "gpt",
    "gpt-image": "gpt",
    "gpt-mini": "gpt",
    "gpt-nano": "gpt",
    "gpt-oss": "gpt",
    "gpt-pro": "gpt",
    "o": "gpt",
    "o-mini": "gpt",
    "o-pro": "gpt",
    "qwen": "qwen",
    "qwen2.5": "qwen",
    "qwen3": "qwen",
    "qwen3-vl": "qwen",
    "qwen3.5": "qwen",
    "qwen3.6": "qwen",
    "kimi": "kimi",
    "kimi-k2.6": "kimi",
    "kimi-thinking": "kimi",
    "minimax": "minimax",
    "minimax-m2.5": "minimax",
    "nova": "nova",
    "nova-lite": "nova",
    "nova-micro": "nova",
    "nova-pro": "nova",
    "trinity": "trinity",
    "trinity-mini": "trinity",
    "gemma": "gemma",
    "gemma3": "gemma",
    "gemma4": "gemma",
    "llama": "llama",
    "llama4": "llama",
    "glm": "glm",
    "glm-air": "glm",
    "glm-flash": "glm",
    "glm-z": "glm",
    "glmv": "glm",
    "command": "command",
    "command-a": "command",
    "command-r": "command",
    "sonar": "sonar",
    "sonar-deep-research": "sonar",
    "sonar-pro": "sonar",
    "sonar-reasoning": "sonar",
    "grok": "grok",
    "grok-beta": "grok",
    "grok-vision": "grok",
    "cohere-embed": "cohere",
    "cohere-rerank": "cohere",
}

# Sub-family → series override (for merged families)
SUBFAMILY_SERIES = {
    "claude": "claude-3",  # the lone claude family card
    "claude-haiku": "haiku",
    "claude-opus": "opus",
    "claude-sonnet": "sonnet",
    "gemini-embedding": "embedding",
    "gemini-flash": "flash",
    "gemini-flash-lite": "flash-lite",
    "gemini-pro": "pro",
    "deepseek-flash": "flash",
    "deepseek-thinking": "thinking",
    "mistral-embed": "embed",
    "mistral-large": "large",
    "mistral-medium": "medium",
    "mistral-nemo": "nemo",
    "mistral-small": "small",
    "mixtral": "mixtral",
    "ministral": "ministral",
    "ministral-3": "ministral-3",
    "magistral-medium": "magistral-medium",
    "magistral-small": "magistral-small",
    "codestral": "codestral",
    "codestral-embed": "codestral-embed",
    "voxtral": "voxtral",
    "pixtral": "pixtral",
    "gpt-codex": "codex",
    "gpt-codex-mini": "codex-mini",
    "gpt-codex-spark": "codex-spark",
    "gpt-image": "image",
    "gpt-mini": "mini",
    "gpt-nano": "nano",
    "gpt-oss": "oss",
    "gpt-pro": "pro",
    "o": "o",
    "o-mini": "o-mini",
    "o-pro": "o-pro",
    "qwen2.5": "qwen2.5",
    "qwen3": "qwen3",
    "qwen3-vl": "qwen3-vl",
    "qwen3.5": "qwen3.5",
    "qwen3.6": "qwen3.6",
    "kimi-k2.6": "k2.6",
    "kimi-thinking": "thinking",
    "minimax-m2.5": "m2.5",
    "nova-lite": "lite",
    "nova-micro": "micro",
    "nova-pro": "pro",
    "trinity-mini": "mini",
    "gemma3": "gemma3",
    "gemma4": "gemma4",
    "llama4": "llama4",
    "glm-air": "air",
    "glm-flash": "flash",
    "glm-z": "z",
    "glmv": "v",
    "command-a": "a",
    "command-r": "r",
    "sonar-deep-research": "deep-research",
    "sonar-pro": "pro",
    "sonar-reasoning": "reasoning",
    "grok-beta": "beta",
    "grok-vision": "vision",
}

# Known provider prefixes to strip before series inference
STRIP_PREFIXES = sorted([
    "accounts-fireworks-models-",
    "accounts-fireworks-routers-",
    "alibaba-",
    "anthropic--",
    "anthropic-",
    "arcee-ai-afm-models-",
    "arcee-ai-",
    "baseten-",
    "bytedance-",
    "cf-",
    "clarifai-main-models-",
    "cohere-cohere-",
    "cohere-",
    "core42-",
    "databricks-",
    "deepseek-ai-",
    "deepcogito-",
    "essentialai-",
    "featherless-ai-",
    "fireworks-",
    "google-",
    "hf-",
    "huihui-ai-",
    "ibm-granite-",
    "ideogramai-",
    "inception-",
    "inclusionai-",
    "inflection-",
    "kblab-",
    "kwaipilot-",
    "liquid-",
    "lucidnova-",
    "lumalabs-",
    "meituan-",
    "meta-llama-llama-",
    "meta-llama-",
    "microsoft-",
    "minimax-",
    "mistralai-",
    "mistral-",
    "moonshotai-chat-completion-models-",
    "moonshotai-",
    "nvidia-",
    "openai-chat-completion-models-",
    "openai-",
    "openrouter-",
    "prime-intellect-",
    "recraft-",
    "rednote-",
    "runwayml-",
    "sourceful-",
    "stabilityai-",
    "stepfun-ai-",
    "thudm-",
    "trytako-",
    "unsloth-",
    "vercel-",
    "voyage-",
    "workers-ai-cf-",
    "workers-ai-",
    "x-ai-",
    "xai-",
    "z-ai-",
    "01-ai-",
    "abacusai-",
    "agentica-org-",
    "ai21-labs-ai21-",
    "ai21-",
    "allenai-",
    "amazon-",
    "arliai-",
    "baai-",
    "baidu-",
    "bfl-",
    "bytedance-research-",
    "bytedance-",
    "chutesai-",
    "cognitivecomputations-",
    "deepcogito-",
    "envoid-",
    "essentialai-",
    "featherless-",
    "galrionsoftworks-",
    "gryphe-",
    "huggingfaceh4-",
    "ibm-",
    "infermatic-",
    "inflatebot-",
    "intel-",
    "kblab-",
    "kwaipilot-",
    "marinaraspaghetti-",
    "meituan-",
    "microsoft-",
    "minimaxai-",
    "mlabonne-",
    "neversleep-",
    "nothingiisreal-",
    "nousresearch-2-",
    "nousresearch-",
    "nvidia-nvidia-",
    "open-r1-",
    "openchat-",
    "paddlepaddle-",
    "pamanseau-",
    "raifle-",
    "readyart-",
    "rednote-hilab-",
    "rekaai-",
    "sao10k-",
    "sapiens-ai-",
    "shisa-ai-",
    "soob3123-",
    "sophosympatheia-",
    "speakleash-",
    "steelskull-",
    "study-",
    "thedrummer-2-",
    "thedrummer-",
    "tongyi-zhiwen-",
    "undi95-",
    "volcengine-",
    "vongolachouko-",
    "xiaomimimo-",
], key=len, reverse=True)

def strip_prefixes(slug):
    for p in STRIP_PREFIXES:
        if slug.startswith(p):
            return slug[len(p):]
    return slug

def infer_series(bare_slug, current_family=None):
    """Infer series name from stripped slug."""
    bare = bare_slug.lower().strip("-")

    # GPT/OpenAI series
    m = re.match(r'^(gpt-\d+(?:\.\d+)?[a-z]*)', bare)
    if m:
        return m.group(1)

    # o-series reasoning models
    m = re.match(r'^(o\d+(?:-[a-z]+)*)', bare)
    if m and not bare.startswith('osmosis'):
        return m.group(1)

    # chatgpt
    if bare.startswith('chatgpt'):
        return 'chatgpt'

    # Qwen series
    m = re.match(r'^(qwen[\d.]*[\w]*(?:-vl)?(?:-coder)?(?:-embedding)?)', bare)
    if m:
        s = m.group(1).rstrip("-")
        s = s.replace("3p6", "3.6").replace("2p5", "2.5").replace("p6", ".6").replace("p5", ".5")
        return s

    # Claude series
    m = re.match(r'^(claude-\d+(?:-\d+)?(?:-\w+)?)', bare)
    if m:
        return m.group(1)

    # Gemini series
    m = re.match(r'^(gemini-\d+(?:\.\d+)?(?:-\w+)?)', bare)
    if m:
        return m.group(1)

    # DeepSeek series
    if bare.startswith("deepseek-"):
        parts = bare.split("-")
        if len(parts) >= 2:
            return f"{parts[0]}-{parts[1]}"

    # Llama series
    if bare.startswith("llama-"):
        rest = bare[6:]
        m = re.match(r'^(\d+(?:\.\d+)?)', rest)
        if m:
            version = m.group(1)
            remainder = rest[m.end():]
            m2 = re.match(r'^-(\d+)(?!\d)(?![bBeE])', remainder)
            if m2:
                version += f"-{m2.group(1)}"
            return f"llama-{version}"

    # Mistral sub-series
    if bare.startswith("mistral-"):
        parts = bare.split("-")
        if len(parts) >= 2:
            return f"{parts[0]}-{parts[1]}"

    # Grok series
    if bare.startswith("grok-"):
        parts = bare.split("-")
        return f"{parts[0]}-{parts[1]}" if len(parts) >= 2 else bare

    # Kimi series
    if bare.startswith("kimi-"):
        parts = bare.split("-")
        return f"{parts[0]}-{parts[1]}" if len(parts) >= 2 else "kimi"

    # GLM series
    if bare.startswith("glm-"):
        parts = bare.split("-")
        return f"{parts[0]}-{parts[1]}" if len(parts) >= 2 else bare

    # Phi series
    if bare.startswith("phi-"):
        return "phi"

    # MiniMax series
    m = re.match(r'^(minimax-\w+)', bare)
    if m:
        return m.group(1)

    # Seed series
    if bare.startswith("seed-"):
        return "seed"

    # Nova series
    if bare.startswith("nova-"):
        return "nova"

    # Pixtral
    if bare.startswith("pixtral"):
        return "pixtral"

    # Cohere series
    if bare.startswith("command-"):
        parts = bare.split("-")
        return f"{parts[0]}-{parts[1]}" if len(parts) >= 2 else bare
    if bare.startswith("rerank"):
        return "rerank"
    if bare.startswith("embed-") or bare.startswith("cohere-embed"):
        return "embed"

    # Flux
    if bare.startswith("flux"):
        return "flux"

    # Sonar / Perplexity
    if bare.startswith("sonar"):
        return re.match(r'^(sonar(?:-\w+)*)', bare).group(1)

    # Fallback: first 2 segments
    parts = bare.split("-")
    if len(parts) >= 2:
        return f"{parts[0]}-{parts[1]}"
    return bare

def infer_family_from_slug(slug):
    """Try to infer broad family from slug pattern (for unknown cards)."""
    bare = strip_prefixes(slug).lower()

    # Check known model prefixes
    if bare.startswith("gpt-") or re.match(r'^o\d+', bare) or bare.startswith("chatgpt"):
        return "gpt"
    if bare.startswith("qwen") or bare.startswith("tongyi"):
        return "qwen"
    if bare.startswith("claude"):
        return "claude"
    if bare.startswith("gemini"):
        return "gemini"
    if bare.startswith("deepseek") and not bare.startswith("deepcogito"):
        return "deepseek"
    if bare.startswith("llama"):
        return "llama"
    if "mistral" in bare or "mixtral" in bare or "ministral" in bare or "codestral" in bare or "magistral" in bare:
        return "mistral"
    if bare.startswith("grok"):
        return "grok"
    if bare.startswith("kimi") or bare.startswith("moonshotai"):
        return "kimi"
    if bare.startswith("glm") or bare.startswith("z-ai-glm"):
        return "glm"
    if bare.startswith("phi-") or bare.startswith("microsoft-phi"):
        return "phi"
    if bare.startswith("minimax"):
        return "minimax"
    if bare.startswith("gemma"):
        return "gemma"
    if bare.startswith("nova"):
        return "nova"
    if bare.startswith("command") or bare.startswith("cohere"):
        return "command"
    if bare.startswith("sonar"):
        return "sonar"
    if bare.startswith("flux") or bare.startswith("bfl-"):
        return "flux"
    if bare.startswith("seed"):
        return "seed"
    if bare.startswith("nemotron"):
        return "nemotron"
    if bare.startswith("mimo"):
        return "mimo"
    if bare.startswith("ernie") or bare.startswith("baidu-"):
        return "ernie"
    if bare.startswith("pixtral"):
        return "mistral"
    if bare.startswith("solar-"):
        return "solar"
    if bare.startswith("trinity"):
        return "trinity"
    if bare.startswith("voyage"):
        return "voyage"
    if bare.startswith("whisper"):
        return "whisper"
    if bare.startswith("yi-") or bare.startswith("01-ai-yi"):
        return "yi"
    if bare.startswith("bert") or bare.startswith("distilbert"):
        return "bert"
    if bare.startswith("jamba"):
        return "jamba"
    if bare.startswith("dbrx") or bare.startswith("databricks-dbrx"):
        return "dbrx"
    if bare.startswith("devstral"):
        return "devstral"
    if bare.startswith("hermes"):
        return "hermes"
    if bare.startswith("nousresearch"):
        return "nousresearch"
    if bare.startswith("solar-"):
        return "solar"
    if bare.startswith("phi") or bare.startswith("microsoft-phi"):
        return "phi"
    if bare.startswith("bge") or bare.startswith("baai-bge"):
        return "bge"
    if bare.startswith("cohere"):
        return "cohere"
    if bare.startswith("elevenlabs"):
        return "elevenlabs"
    if bare.startswith("deepgram") or bare.startswith("aura"):
        return "aura"
    if "nemotron" in bare:
        return "nemotron"
    if bare.startswith("unsloth"):
        return "unsloth"

    return None

def read_frontmatter(path):
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

def write_frontmatter(path, data, body):
    with open(path, "w") as f:
        f.write("---\n")
        f.write(yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False).rstrip())
        f.write("\n---\n")
        if body:
            f.write(body.strip() + "\n")

def collect_cards():
    """Return list of (current_family, slug, path, frontmatter, body) tuples."""
    cards = []
    for root, dirs, files in os.walk(MODELS_DIR):
        for fn in sorted(files):
            if not fn.endswith(".md"):
                continue
            path = os.path.join(root, fn)
            slug = fn[:-3]
            rel = os.path.relpath(root, MODELS_DIR)
            cur_family = rel if rel != "." else "unknown"
            data, body = read_frontmatter(path)
            cards.append((cur_family, slug, path, data, body))
    return cards

def get_provider_refs():
    """Read all provider models.md files and return {provider: [(old_ref, line)]}."""
    refs = {}
    for d in os.listdir(BASE):
        pdir = os.path.join(BASE, d)
        mdfile = os.path.join(pdir, "models.md")
        if not os.path.isdir(pdir) or not os.path.exists(mdfile):
            continue
        if d in ("models", "scripts") or d.startswith("."):
            continue
        with open(mdfile) as f:
            lines = f.readlines()
        refs[d] = lines
    return refs

def main():
    apply = "--apply" in sys.argv

    cards = collect_cards()
    old_provider_refs = get_provider_refs()

    # Phase 1: determine new family + series for each card
    moves = []  # (old_path, new_family, new_series, new_slug_path, data, body)
    stats = defaultdict(lambda: {"moved": 0, "family_changed": 0, "series_added": 0, "series_inferred": 0})

    for cur_family, slug, old_path, data, body in cards:
        # Determine broad family (try inference for unknown)
        broad_family = cur_family
        if cur_family == "unknown":
            inferred = infer_family_from_slug(slug)
            if inferred:
                broad_family = inferred
        elif cur_family in FAMILY_MERGE_MAP:
            broad_family = FAMILY_MERGE_MAP[cur_family]

        # Determine series
        frontmatter_family = data.get("family", cur_family)
        series = data.get("series")

        if series:
            # Already has a series field
            pass
        elif cur_family in SUBFAMILY_SERIES:
            # Card is in a merged sub-family → use predefined series name
            series = SUBFAMILY_SERIES[cur_family]
            stats[broad_family]["series_inferred"] += 1
        elif broad_family != cur_family:
            # Family was changed but no subfamily series defined
            bare = strip_prefixes(slug)
            series = infer_series(bare)
            stats[broad_family]["series_inferred"] += 1
        else:
            # Same family, infer series from slug
            bare = strip_prefixes(slug)
            series = infer_series(bare)
            stats[broad_family]["series_inferred"] += 1

        if not series:
            series = "unknown"

        # Update frontmatter
        changed = False
        if data.get("family") != broad_family:
            data["family"] = broad_family
            stats[broad_family]["family_changed"] += 1
            changed = True
        if not data.get("series") or data["series"] != series:
            data["series"] = series
            stats[broad_family]["series_added"] += 1
            changed = True

        new_path = os.path.join(MODELS_DIR, broad_family, series, f"{slug}.md")
        if new_path != old_path:
            stats[broad_family]["moved"] += 1

        moves.append((old_path, broad_family, series, new_path, data, body, changed))

    # Phase 2: print plan
    total_moved = sum(s["moved"] for s in stats.values())
    total_family_changed = sum(s["family_changed"] for s in stats.values())
    total_series_added = sum(s["series_added"] for s in stats.values())

    print(f"Cards to restructure: {len(moves)}")
    print(f"  Move to new path:  {total_moved}")
    print(f"  Family updated:    {total_family_changed}")
    print(f"  Series added:      {total_series_added}")
    print()
    print("Breakdown by family:")
    for broad in sorted(stats):
        s = stats[broad]
        if s["moved"] or s["family_changed"] or s["series_added"]:
            parts = []
            if s["moved"]: parts.append(f"move={s['moved']}")
            if s["family_changed"]: parts.append(f"fam={s['family_changed']}")
            if s["series_added"]: parts.append(f"series={s['series_added']}")
            print(f"  {broad}: {', '.join(parts)}")

    if not apply:
        print("\nDry-run complete. Run with --apply to execute.")
        return

    # Phase 3: Execute moves
    for old_path, broad_family, series, new_path, data, body, changed in moves:
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        if new_path != old_path:
            # Remove old file
            if os.path.exists(new_path):
                print(f"  WARN: target exists, overwriting: {new_path}")
            if os.path.exists(old_path):
                os.remove(old_path)
        write_frontmatter(new_path, data, body)

    # Phase 4: Clean up empty directories
    removed_dirs = 0
    for root, dirs, files in os.walk(MODELS_DIR, topdown=False):
        if root == MODELS_DIR:
            continue
        if not os.path.exists(root):
            continue
        remaining = os.listdir(root)
        remaining = [r for r in remaining if not r.startswith(".")]
        if not remaining:
            os.rmdir(root)
            removed_dirs += 1

    print(f"\nRemoved empty directories: {removed_dirs}")

    # Phase 5: Update provider refs
    # Build old_slug → new_ref mapping
    slug_to_new = {}
    for old_path, broad_family, series, new_path, data, body, changed in moves:
        slug = old_path.rsplit("/", 1)[-1][:-3]
        slug_to_new[slug] = f"{broad_family}/{series}/{slug}"

    refs_updated = 0
    for prov, lines in old_provider_refs.items():
        new_lines = []
        mod = False
        for line in lines:
            m = re.match(r'^(\s+- name:\s+)(.+)', line)
            if m:
                prefix, entry = m.group(1), m.group(2).strip()
                old_slug = entry.split("/")[-1]
                if old_slug in slug_to_new:
                    new_entry = slug_to_new[old_slug]
                    if entry != new_entry:
                        new_lines.append(f"{prefix}{new_entry}\n")
                        mod = True
                        refs_updated += 1
                        continue
            new_lines.append(line)
        if mod:
            with open(os.path.join(BASE, prov, "models.md"), "w") as f:
                f.writelines(new_lines)

    print(f"Provider refs updated: {refs_updated}")

    # Phase 6: Create README.md per family
    readme_dirs = set()
    for old_path, broad_family, series, new_path, data, body, changed in moves:
        readme_dirs.add(broad_family)

    for family in sorted(readme_dirs):
        fam_path = os.path.join(MODELS_DIR, family)
        readme_path = os.path.join(fam_path, "README.md")
        if os.path.exists(readme_path):
            continue

        # Count cards per series
        series_counts = defaultdict(int)
        for old_path, bf, series, new_path, data, body, changed in moves:
            if bf == family:
                series_counts[series] += 1

        lines = [f"# {family.title()}\n\n"]
        lines.append(f"Model cards for the **{family}** family ({sum(series_counts.values())} total).\n\n")
        for s in sorted(series_counts):
            lines.append(f"- [{s}]({s}/) — {series_counts[s]} model(s)\n")

        with open(readme_path, "w") as f:
            f.writelines(lines)

    print(f"Family README.md files created: {len(readme_dirs)}")
    print("\nDone!")

if __name__ == "__main__":
    main()
