"""
One-shot enrichment: add structured free-tier fields to all provider.md files.

Extracts free tier info from existing descriptions, applies a curated
FREE_CREDIT_MAP, and sets `free: true` on models.md entries for
free-tier providers.

Usage:
    python3 scripts/enrich_free_info.py          # dry-run
    python3 scripts/enrich_free_info.py --apply  # write changes
"""

import os, re, sys, yaml
from collections import defaultdict

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Curated free-credit map ───────────────────────────────────────────
# Fields: free_credit (str), requires_credit_card (bool)
FREE_CREDIT_MAP = {
    "google": {"free_credit": "$300 credit for new users", "requires_credit_card": True},
    "openai": {"free_credit": "$5 credit (expires 3 months)", "requires_credit_card": False},
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
    "llm7": {"free_credit": "No registration needed for basic access", "requires_credit_card": False},
    "kilo": {"free_credit": "Free models with no credit card required", "requires_credit_card": False},
    "poe": {"free_credit": "Free and subscription-based access", "requires_credit_card": False},
    "chutes": {"free_credit": "Free and paid tiers for community models", "requires_credit_card": False},
    "aion": {"free_credit": "Free daily token allowance, no credit card required", "requires_credit_card": False},
    "openrouter": {"free_credit": "~28 free models (marked with :free suffix)", "requires_credit_card": False},
    "kluster-ai": {"free_credit": "Free tier (undocumented limits)", "requires_credit_card": False},
    "novita": {"free_credit": "Free tier with rate limits", "requires_credit_card": False},
}


def parse_frontmatter(path):
    with open(path) as f:
        content = f.read()
    m = re.match(r'^---\n(.+?)\n---\n?(.*)', content, re.DOTALL)
    if not m:
        return {}, content, content
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except Exception:
        data = {}
    return data, m.group(2), content


def write_frontmatter(path, data, body):
    with open(path, "w") as f:
        f.write("---\n")
        f.write(yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False).rstrip())
        f.write("\n---\n")
        if body:
            f.write(body.strip() + "\n")


def extract_free_tier_from_desc(desc):
    """Parse existing description for free tier info."""
    desc_lower = desc.lower()
    result = {}

    # Check if free tier exists
    has_free = any(word in desc_lower for word in [
        "free tier", "free trial", "free token", "free model", "free credit",
        "free api", "free anonymous", "free daily", "free signup",
        "no credit card", "no registration", "free prototyping",
        "free for", "no signup", ":free", "free and paid",
    ])
    if has_free:
        result["free_tier"] = True

    # Extract free tier limits (rate limits)
    limits_match = re.search(r'Free tier limits:\s*([^.!]+?)(?:\.\s|\.$|$)', desc)
    if limits_match:
        result["free_tier_description"] = limits_match.group(1).strip()
    elif has_free:
        # Look for RPM/RPD patterns
        rpm_match = re.search(r'(\d+\s*(?:RPM|RPD|req/min|req/day|tokens/day|tokens/month|neurons/day))', desc, re.IGNORECASE)
        if rpm_match:
            result["free_tier_description"] = rpm_match.group(1)

    # Extract credit info
    credit_match = re.search(r'\$?(\d+[KMBkmb]?\s*(?:free|trial|signup|sign-up|credit)s?[^.]*?(?:credit|token|call|request)s?[^.]*?)(?:\.|$)', desc)
    if not credit_match:
        credit_match = re.search(r'([^.]*?(?:\$[\d,]+(?:\.\d+)?[^.]*?(?:credit|token|call|request|signup|trial)[^.]*?))(?:\.|$)', desc)
    if not credit_match:
        credit_match = re.search(r'([^.]*?(?:free\s+\w+\s+token|no\s+credit\s+card|no\s+registration)[^.]*?)(?:\.|$)', desc)
    if credit_match:
        extracted = credit_match.group(1).strip()
        if extracted:
            result["_free_credit_extracted"] = extracted

    # Check requires credit card
    if re.search(r'no credit card|no credit card required|no credit card\.', desc_lower):
        result["requires_credit_card"] = False
    elif re.search(r'requires (a )?credit card|credit card required|credit card needed', desc_lower):
        result["requires_credit_card"] = True
    elif "credit card" in desc_lower:
        # Mentioned but unclear — leave as None for manual review
        pass

    return result


def main():
    apply = "--apply" in sys.argv

    # Collect all providers
    providers = []
    for d in sorted(os.listdir(BASE)):
        pdir = os.path.join(BASE, d)
        mdfile = os.path.join(pdir, "provider.md")
        models_file = os.path.join(pdir, "models.md")
        if not os.path.isdir(pdir) or not os.path.exists(mdfile):
            continue
        if d in ("models", "scripts") or d.startswith("."):
            continue
        providers.append((d, mdfile, models_file))

    changes = 0
    free_tier_providers = []

    for slug, mdfile, models_file in providers:
        data, body, full = parse_frontmatter(mdfile)

        # Skip if already has structured free-tier fields
        if data.get("free_tier") is not None and data.get("free_credit"):
            continue

        desc = body.strip()
        extracted = extract_free_tier_from_desc(desc)
        credit_map = FREE_CREDIT_MAP.get(slug, {})

        # Build new fields
        modified = False

        # free_tier
        if data.get("free_tier") is None:
            if extracted.get("free_tier"):
                data["free_tier"] = True
                modified = True
            elif credit_map.get("free_credit"):
                data["free_tier"] = True
                modified = True

        # free_tier_description
        if data.get("free_tier_description") is None and extracted.get("free_tier_description"):
            data["free_tier_description"] = extracted["free_tier_description"]
            modified = True

        # free_credit
        if data.get("free_credit") is None:
            if credit_map.get("free_credit"):
                data["free_credit"] = credit_map["free_credit"]
                modified = True
            elif extracted.get("_free_credit_extracted"):
                data["free_credit"] = extracted["_free_credit_extracted"]
                modified = True

        # requires_credit_card
        if data.get("requires_credit_card") is None:
            if extracted.get("requires_credit_card") is not None:
                data["requires_credit_card"] = extracted["requires_credit_card"]
                modified = True
            elif credit_map.get("requires_credit_card") is not None:
                data["requires_credit_card"] = credit_map["requires_credit_card"]
                modified = True

        if not modified:
            continue

        if apply:
            write_frontmatter(mdfile, data, desc)
        else:
            print(f"  {slug}:")
            if "free_tier" in data:
                print(f"    free_tier: {data.get('free_tier')}")
            if data.get("free_tier_description"):
                print(f"    free_tier_description: {data['free_tier_description']}")
            if data.get("free_credit"):
                print(f"    free_credit: {data['free_credit']}")
            if data.get("requires_credit_card") is not None:
                print(f"    requires_credit_card: {data['requires_credit_card']}")

        changes += 1
        if data.get("free_tier"):
            free_tier_providers.append(slug)

    # Phase 2: set free: true on models.md entries for free-tier providers
    if apply:
        model_flag_changes = 0
        for slug in free_tier_providers:
            models_file = os.path.join(BASE, slug, "models.md")
            if not os.path.exists(models_file):
                continue
            with open(models_file) as f:
                lines = f.readlines()

            new_lines = []
            mod = False
            for line in lines:
                m = re.match(r'^(\s+- name:\s+)(.+)', line)
                if m:
                    prefix, entry = m.group(1), m.group(2).strip()
                    # Check if free flag already exists
                    new_lines.append(line.rstrip("\n"))
                    # Look ahead for free: true
                    idx = lines.index(line) if line in lines else -1
                    has_free = False
                    if idx >= 0 and idx + 1 < len(lines):
                        has_free = "free:" in lines[idx + 1]
                    if not has_free:
                        new_lines.append(f"    free: true")
                        mod = True
                else:
                    new_lines.append(line.rstrip("\n"))
            if mod:
                with open(models_file, "w") as f:
                    f.write("\n".join(new_lines) + "\n")
                model_flag_changes += 1

        print(f"\nModel flag updates: {model_flag_changes} providers")
    else:
        print(f"\nWould flag models for {len(free_tier_providers)} providers as free")

    print(f"\nProviders updated: {changes}" + (" (dry-run)" if not apply else ""))


if __name__ == "__main__":
    main()
