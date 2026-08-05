"""
Extract provider metadata from NousResearch/hermes-agent model-providers.

Source: https://github.com/NousResearch/hermes-agent/tree/main/plugins/model-providers

Each provider plugin has an __init__.py that registers a ProviderProfile with:
  - name, aliases, display_name, description
  - env_vars, base_url, signup_url, auth_type
  - fallback_models, default_aux_model, models_url

Usage:
    python3 scripts/generate_from_hermes_agent.py          # use cached
    python3 scripts/generate_from_hermes_agent.py --fetch  # re-fetch
"""

import ast, json, os, re, subprocess, sys, textwrap, yaml

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_DIR = os.path.join(BASE, "raw", "hermes-agent-cache")
os.makedirs(CACHE_DIR, exist_ok=True)

REPO_API = "https://api.github.com/repos/NousResearch/hermes-agent/contents/plugins/model-providers"
RAW_BASE = "https://raw.githubusercontent.com/NousResearch/hermes-agent/main/plugins/model-providers"

def sanitize(s):
    s = re.sub(r'[^a-z0-9-]', '-', s.lower().replace(':', '-').replace('/', '-').replace('_', '-').replace('.', '-').replace(' ', '-'))
    return s.strip('-')

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


def find_card(slug):
    """Find a model card by slug in the models directory (flat)."""
    models_dir = os.path.join(BASE, "raw", "models")
    fpath = os.path.join(models_dir, f"{slug}.md")
    if os.path.exists(fpath):
        return fpath
    return None


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


def fetch_manifests():
    """Fetch list of provider directories from GitHub API."""
    import urllib.request
    req = urllib.request.Request(REPO_API, headers={"User-Agent": "opencode"})
    with urllib.request.urlopen(req) as resp:
        entries = json.loads(resp.read())
    providers = []
    for e in entries:
        if e["type"] == "dir" and e["name"] not in (".", "..", ".github"):
            providers.append(e["name"])
    return providers

def fetch_init(pname):
    """Fetch __init__.py for a provider plugin."""
    url = f"{RAW_BASE}/{pname}/__init__.py"
    dest = os.path.join(CACHE_DIR, f"{pname}.py")
    subprocess.run(["curl", "-sSL", url, "-o", dest], check=True)
    return dest

def extract_provider_args(filepath):
    """Parse __init__.py AST to extract ProviderProfile constructor kwargs.

    Returns a list of dicts, one per register_provider() call.
    Follows variable assignments to find the actual constructor call.
    """
    with open(filepath) as f:
        source = f.read()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    results = []
    # Track module-level assignments: name -> node
    assignments = {}

    class ModuleScanner(ast.NodeVisitor):
        def visit_Assign(self, node):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                assignments[node.targets[0].id] = node.value
            self.generic_visit(node)

    ModuleScanner().visit(tree)

    class CallVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            if (isinstance(node.func, ast.Name) and node.func.id == "register_provider"
            ) or (isinstance(node.func, ast.Attribute) and node.func.attr == "register_provider"):
                if node.args:
                    self._extract_profile(node.args[0])
            self.generic_visit(node)

        def _extract_profile(self, node):
            if isinstance(node, ast.Call):
                kwargs = {}
                for kw in node.keywords:
                    if kw.arg is None:
                        continue
                    kwargs[kw.arg] = self._eval_node(kw.value)
                if "name" in kwargs:
                    results.append(kwargs)
            elif isinstance(node, ast.Name):
                var_name = node.id
                if var_name in assignments:
                    self._extract_profile(assignments[var_name])

        def _eval_node(self, node):
            if isinstance(node, ast.Constant):
                return node.value
            elif isinstance(node, ast.Tuple):
                return tuple(self._eval_node(e) for e in node.elts)
            elif isinstance(node, ast.List):
                return [self._eval_node(e) for e in node.elts]
            elif isinstance(node, ast.Dict):
                return {self._eval_node(k): self._eval_node(v) for k, v in zip(node.keys, node.values)}
            elif isinstance(node, ast.Name):
                return node.id
            elif isinstance(node, ast.Attribute):
                return f"{self._eval_node(node.value)}.{node.attr}" if isinstance(node.value, ast.Name) else node.attr
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
                val = self._eval_node(node.operand)
                return -val if isinstance(val, (int, float)) else val
            elif isinstance(node, ast.BinOp):
                left = self._eval_node(node.left)
                right = self._eval_node(node.right)
                if isinstance(node.op, ast.Add):
                    return (left or "") + (right or "")
                return None
            return None

    CallVisitor().visit(tree)
    return results

def main():
    if "--fetch" in sys.argv:
        pass  # will fetch below

    # Get provider list
    if not os.path.exists(CACHE_DIR) or "--fetch" in sys.argv:
        providers = fetch_manifests()
        meta_path = os.path.join(CACHE_DIR, "providers.json")
        with open(meta_path, "w") as f:
            json.dump(providers, f)
        print(f"  Found {len(providers)} provider plugins")
        for p in providers:
            fetch_init(p)
        print(f"  Fetched {len(providers)} __init__.py files")
    else:
        with open(os.path.join(CACHE_DIR, "providers.json")) as f:
            providers = json.load(f)

    # Parse all provider profiles
    all_profiles = []
    for pname in sorted(providers):
        fpath = os.path.join(CACHE_DIR, f"{pname}.py")
        if not os.path.exists(fpath):
            continue
        profiles = extract_provider_args(fpath)
        for prof in profiles:
            prof["_plugin_name"] = pname
            all_profiles.append(prof)
            print(f"  Parsed: {prof.get('name', '?')} (aliases={prof.get('aliases', ())})")

    print(f"\n  Total profiles extracted: {len(all_profiles)}")

    # Update provider dirs in providers/
    existing = set()
    providers_dir = os.path.join(BASE, "raw", "providers")
    if os.path.exists(providers_dir):
        for d in os.listdir(providers_dir):
            if os.path.isdir(os.path.join(providers_dir, d)):
                if os.path.exists(os.path.join(providers_dir, d, "provider.md")):
                    existing.add(d)

    updated = 0
    new_providers = 0
    models_dir = os.path.join(BASE, "raw", "models")
    os.makedirs(models_dir, exist_ok=True)

    for prof in all_profiles:
        name = prof.get("name", "")
        slug = sanitize(name)
        aliases = prof.get("aliases", ())
        display_name = prof.get("display_name") or name
        description = prof.get("description") or ""
        base_url = prof.get("base_url") or ""
        signup_url = prof.get("signup_url") or ""
        env_vars = prof.get("env_vars", ())
        fallback_models = prof.get("fallback_models", ())
        default_aux = prof.get("default_aux_model", "")
        auth_type = prof.get("auth_type", "")
        models_url = prof.get("models_url", "")

        # Try to match existing slug via aliases
        target_slug = slug
        if slug not in existing:
            for alias in aliases:
                aslug = sanitize(alias)
                if aslug in existing:
                    target_slug = aslug
                    break

        pdir = os.path.join(BASE, "raw", "providers", target_slug)
        is_new = target_slug not in existing
        if is_new:
            os.makedirs(pdir, exist_ok=True)

        md_path = os.path.join(pdir, "provider.md")
        existing_url = ""
        existing_desc = ""
        preserved = {}
        if os.path.exists(md_path):
            with open(md_path) as f:
                content = f.read()
            parts = content.split("---\n")
            if len(parts) >= 3:
                existing_desc = parts[-1].strip()
                for line in parts[1].split("\n"):
                    if line.startswith("url:"):
                        u = line.split(":", 1)[1].strip().strip('"').strip("'")
                        if u:
                            existing_url = u
                try:
                    existing_fm = yaml.safe_load(parts[1])
                    if isinstance(existing_fm, dict):
                        for key in ("free_tier", "free_tier_description", "free_credit", "requires_credit_card"):
                            if key in existing_fm:
                                preserved[key] = existing_fm[key]
                except Exception:
                    pass

        new_url = base_url or existing_url
        extra_info = []
        if env_vars:
            extra_info.append(f"Auth via {' or '.join(env_vars)}")
        if signup_url:
            extra_info.append(f"Signup: {signup_url}")
        if auth_type:
            extra_info.append(f"Auth type: {auth_type}")
        if fallback_models:
            extra_info.append(f"Default models: {', '.join(fallback_models[:3])}")
        if models_url:
            extra_info.append(f"Models API: {models_url}")

        merged_desc = existing_desc or description
        if extra_info:
            suffix = ". " + ". ".join(extra_info) + "."
            merged_desc = merged_desc.rstrip(".") + suffix if merged_desc else ". ".join(extra_info) + "."

        with open(md_path, "w") as f:
            fm = {"name": display_name, "url": new_url, "self_hosted": False}
            fm.update(preserved)
            f.write("---\n" + yaml.dump(fm, default_flow_style=False, allow_unicode=True).strip() + "\n---\n" + merged_desc + "\n")

        # Update model cards with fallback models
        for fm in fallback_models:
            mslug = sanitize(fm)
            mfile = find_card(mslug)
            if not mfile:
                # Create minimal model card in flat models/ directory
                family = infer_family(mslug)
                series = infer_series(mslug)
                mfile = os.path.join(models_dir, f"{mslug}.md")
                with open(mfile, "w") as f:
                    f.write(f"---\nname: {mslug}\nfamily: {family}\nseries: {series}\nvision: false\n")
                    f.write("supports_reasoning: false\nsupports_tool_call: false\n")
                    f.write("open_weights: false\nself_hosted: false\nproviders: []\n")
                    f.write(f"---\n{fm} (fallback for {display_name})\n")
                print(f"    Created model card: {mslug}")
            else:
                # Update existing: add this provider if not listed
                with open(mfile) as f:
                    content = f.read()
                if target_slug in content:
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
                        new_lines.insert(len(new_lines) - 1, f"  - {target_slug}")
                        in_providers = False
                        added = True
                if not added and in_providers:
                    new_lines.append(f"  - {target_slug}")
                with open(mfile, "w") as f:
                    f.write("\n".join(new_lines))

        if is_new:
            new_providers += 1
            print(f"  NEW: {target_slug} ({display_name})")
        else:
            updated += 1

    print(f"\nDone! Updated {updated} existing providers, created {new_providers} new")

if __name__ == "__main__":
    main()