"""
Deduplicate model cards by normalizing provider-specific name variants.

Many model cards exist with provider-namespaced slugs (e.g., cf-llama-3-8b-instruct,
hf-meta-llama-llama-3-8b-instruct) that represent the same model as the bare slug
(llama-3-8b-instruct). This script detects those duplicates, merges provider
references AND metadata into the best canonical card, and removes the duplicates.

Metadata-aware: cards with conflicting context_length, family, total_parameters,
or boolean capabilities are NOT merged — they are treated as distinct models.

Usage:
    python3 scripts/dedup_model_cards.py          # show what would be merged (dry-run)
    python3 scripts/dedup_model_cards.py --apply  # actually perform the merge
"""

import os, re, sys, yaml

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(BASE, "models")

# Known provider prefixes that are safe to strip
PREFIXES = sorted([
    "accounts-fireworks-models-",
    "alibaba-",
    "workers-ai-cf-",
    "google-gemini-",
    "openai-chat-completion-models-",
    "mistralai-completion-models-",
    "meta-llama-meta-llama-",
    "meta-llama-llama-",
    "hf-",
    "cf-",
    "deepseek-ai-",
    "mistralai-",
    "minimaxai-",
    "moonshotai-",
    "nousresearch-",
    "cognitivecomputations-",
    "nousresearch-2-",
    "openai-",
    "nvidia-",
    "nvidia-nvidia-",
    "sophosympatheia-",
    "gryphe-",
    "featherless-",
    "featherless-ai-",
    "agentica-org-",
    "arliai-",
    "thedrummer-",
    "thedrummer-2-",
    "undi95-",
    "shisa-ai-",
    "bytedance-research-",
    "allenai-",
    "open-r1-",
    "openchat-",
    "liquid-",
    "chutesai-",
    "huggingfaceh4-",
    "microsoft-",
    "xai-",
    "x-ai-",
    "rekaai-",
    "inclusionai-",
    "study-",
    "sapiens-ai-",
    "speakleash-",
    "volcengine-",
    "xiaomimimo-",
    "infermatic-",
    "steelskull-",
    "inflatebot-",
    "topazlabs-co-",
    "marinaraspaghetti-",
    "trytako-",
    "soob3123-",
    "raifle-",
    "neversleep-",
    "nothingiisreal-",
    "pamanseau-",
    "mlabonne-",
    "kwaipilot-",
    "readyart-",
    "rednote-hilab-",
    "paddlepaddle-",
    "thudm-",
    "tongyi-zhiwen-",
    "sao10k-",
    "vongolachouko-",
    "huihui-ai-",
    "olafangensan-",
    "galrionsoftworks-",
    "eva-unit-01-",
    "empiriolabs-",
    "recraft-",
    "stabilityai-",
    "ideogramai-",
    "runwayml-",
    "lucidnova-",
    "lucidquery-",
    "meganova-ai-",
    "tngtech-",
    "failspy-",
    "novita-",
    "salesforce-",
    "latitudegames-",
    "intel-",
    "morph-",
    "essentialai-",
    "elevenlabs-",
    "perplexity-",
    "meituan-",
    "mercury-",
    "vercel-",
    "primedolphin-",
    "nex-agi-",
    "poetools-",
    "osmosis-",
    "sarvam-",
    "interfaze-",
], key=len, reverse=True)

TRAILING = ["-free", ":free", "-deprecated", ":deprecated", "-max"]


def sanitize(s):
    return re.sub(r'[^a-z0-9-]', '-', s.lower().replace(':', '-').replace('/', '-').replace('_', '-').replace('.', '-').replace(' ', '-')).strip('-')


def normalize_candidates(slug):
    candidates = [slug]
    stripped = slug
    for t in TRAILING:
        if stripped.endswith(t):
            stripped = stripped[:-len(t)]
            candidates.append(stripped)
            break
    for p in PREFIXES:
        if stripped.startswith(p):
            rest = stripped[len(p):]
            if rest:
                candidates.append(rest)
            break
    parts = stripped.split("-")
    if len(parts) >= 3 and parts[0] == parts[1]:
        candidates.append("-".join(parts[1:]))
    return candidates


def parse_card(path):
    """Return (frontmatter_dict, body_str) or (None, None) on failure."""
    with open(path) as f:
        content = f.read()
    m = re.match(r'^---\n(.+?)\n---\n?(.*)', content, re.DOTALL)
    if not m:
        return None, None
    try:
        data = yaml.safe_load(m.group(1))
    except Exception:
        return None, None
    return data or {}, m.group(2)


def metadata_compatible(a, b):
    """Check whether two cards' metadata suggests they represent the same model."""
    # family must match if both are defined and neither is "unknown"
    af = a.get("family", "").lower().strip()
    bf = b.get("family", "").lower().strip()
    if af and bf and af != bf and af != "unknown" and bf != "unknown":
        return False

    # context_length must be within 20% if both defined
    actx = a.get("context_length")
    bctx = b.get("context_length")
    if actx is not None and bctx is not None and actx > 0 and bctx > 0:
        ratio = max(actx, bctx) / min(actx, bctx)
        if ratio > 1.20:
            return False

    # total_parameters must match if both defined
    ap = a.get("total_parameters")
    bp = b.get("total_parameters")
    if ap is not None and bp is not None and ap > 0 and bp > 0:
        ratio = max(ap, bp) / min(ap, bp)
        if ratio > 1.10:
            return False

    # active_parameters must match if both defined
    aa = a.get("active_parameters")
    ba = b.get("active_parameters")
    if aa is not None and ba is not None and aa > 0 and ba > 0:
        if aa != ba:
            if max(aa, ba) / min(aa, ba) > 1.10:
                return False

    # vision: if one explicitly true and other explicitly false, they differ
    av = a.get("vision")
    bv = b.get("vision")
    if av is not None and bv is not None and av != bv:
        return False

    return True


def merge_metadata(canon_data, dup_data):
    """Merge duplicate's metadata into canonical (mutates canon_data in place)."""
    # Numeric/int fields: prefer non-zero/non-default
    for key in ("context_length", "total_parameters", "active_parameters"):
        cv = canon_data.get(key)
        dv = dup_data.get(key)
        if dv is not None and dv:
            if cv is None or not cv:
                canon_data[key] = dv
            elif key == "context_length":
                canon_data[key] = max(cv, dv)
    # String fields: copy if canonical missing
    for key in ("quantization",):
        if key in dup_data and key not in canon_data:
            canon_data[key] = dup_data[key]
    # Aliases: union
    ca = canon_data.get("aliases", []) or []
    da = dup_data.get("aliases", []) or []
    if da:
        merged = list(dict.fromkeys(ca + da))
        canon_data["aliases"] = merged
    # Boolean fields: prefer True over False
    for key in ("vision", "supports_reasoning", "supports_tool_call", "open_weights", "self_hosted"):
        cv = canon_data.get(key)
        dv = dup_data.get(key)
        if dv is True and cv is False:
            canon_data[key] = True
    # Family: prefer more specific (longer)
    cv = (canon_data.get("family") or "").strip()
    dv = (dup_data.get("family") or "").strip()
    if dv and dv != "unknown" and (not cv or cv == "unknown" or len(dv) > len(cv)):
        canon_data["family"] = dv


def card_path(slug):
    """Find a model card by slug, searching subdirectories recursively."""
    for root, dirs, files in os.walk(MODELS_DIR):
        for fname in files:
            if fname == f"{slug}.md":
                return os.path.join(root, fname)
    return os.path.join(MODELS_DIR, f"{slug}.md")  # fallback


def main():
    dry_run = "--apply" not in sys.argv

    # Walk subdirectories recursively
    all_slugs = []
    for root, dirs, files in os.walk(MODELS_DIR):
        for fname in files:
            if fname.endswith(".md"):
                all_slugs.append(fname[:-3])
    all_slugs = sorted(set(all_slugs))
    slug_set = set(all_slugs)

    # Parse all card metadata upfront
    card_meta = {}
    for slug in all_slugs:
        data, _ = parse_card(card_path(slug))
        card_meta[slug] = data or {}

    # Normalization pass: group cards by their slug similarity, respecting metadata
    groups = []  # list of (canonical_slug, [member_slug, ...])
    assigned = set()

    for slug in all_slugs:
        if slug in assigned:
            continue
        cands = normalize_candidates(slug)
        # Use the raw slug as the "name" key — we'll check metadata to refine
        base_canonical = min((c for c in cands if c in slug_set), key=lambda c: (c.count("-"), len(c)))
        # Look for all cards that normalize to the same canonical
        group_members = []
        for other in all_slugs:
            if other in assigned:
                continue
            ocands = normalize_candidates(other)
            obase = min((c for c in ocands if c in slug_set), key=lambda c: (c.count("-"), len(c)))
            if obase == base_canonical:
                group_members.append(other)

        # Metadata compatibility filtering: split groups on metadata conflicts
        sub_groups = []  # list of lists
        for m in group_members:
            placed = False
            for sg in sub_groups:
                if metadata_compatible(card_meta[sg[0]], card_meta[m]):
                    sg.append(m)
                    placed = True
                    break
            if not placed:
                sub_groups.append([m])

        for sg in sub_groups:
            # Canonical = fewest hyphens, shortest
            canon = min(sg, key=lambda c: (c.count("-"), len(c)))
            groups.append((canon, sg))
            for m in sg:
                assigned.add(m)

    slug_to_norm = {}
    for canon, members in groups:
        for m in members:
            slug_to_norm[m] = canon

    dup_groups = {k: v for k, v in groups if len(v) > 1}
    dup_groups = dict(sorted(dup_groups.items()))
    total_dups = sum(len(v) - 1 for v in dup_groups.values())

    print(f"Total model cards: {len(all_slugs)}")
    print(f"Unique canonical names: {len(groups)}")
    print(f"Duplicate groups: {len(dup_groups)}")
    print(f"Cards that would be removed: {total_dups}")
    print(f"Cards remaining after dedup: {len(all_slugs) - total_dups}")
    print()

    for canonical, members in dup_groups.items():
        dups = [m for m in members if m != canonical]
        print(f"  [{len(dups)} dup] {canonical} ← {', '.join(dups[:5])}{'...' if len(dups)>5 else ''}")

    if dry_run:
        print(f"\nDry-run complete. Run with --apply to merge.")
        return

    # --- APPLY: merge duplicates into canonical cards ---
    to_remove = set()
    for canonical, members in dup_groups.items():
        for dup_slug in members:
            if dup_slug == canonical:
                continue
            to_remove.add(dup_slug)

            dup_path = card_path(dup_slug)
            canon_path = card_path(canonical)

            if not os.path.exists(dup_path):
                continue

            # Read both cards' YAML frontmatter
            dup_data, dup_body = parse_card(dup_path)
            canon_data, canon_body = parse_card(canon_path)

            if not dup_data or not canon_data:
                continue

            # Merge metadata
            merge_metadata(canon_data, dup_data)

            # Merge providers
            dup_providers = set(dup_data.get("providers", []) or [])
            canon_providers = set(canon_data.get("providers", []) or [])
            missing = sorted(dup_providers - canon_providers)
            if missing:
                canon_data["providers"] = sorted(canon_providers | dup_providers)

            # Write updated canonical card
            with open(canon_path, "w") as f:
                f.write("---\n")
                f.write(yaml.dump(canon_data, default_flow_style=False, allow_unicode=True, sort_keys=False).rstrip())
                f.write("\n---\n")
                # Keep the best (longer) description
                if len(dup_body or "") > len(canon_body or ""):
                    f.write(dup_body.strip() + "\n")
                elif canon_body:
                    f.write(canon_body.strip() + "\n")

            if missing:
                print(f"  Merged provider(s) {', '.join(missing)} into {canonical}")
            if os.path.getsize(dup_path) > os.path.getsize(canon_path):
                print(f"  Merged metadata from {dup_slug} into {canonical}")

            # Remove duplicate
            os.remove(dup_path)

    # Build a map of canonical slug → its family/series directories
    def family_of(slug):
        p = card_path(slug)
        if p and os.path.exists(p):
            return os.path.basename(os.path.dirname(os.path.dirname(p)))
        return None

    def series_of(slug):
        p = card_path(slug)
        if p and os.path.exists(p):
            return os.path.basename(os.path.dirname(p))
        return None

    # Update all provider models.md files to use canonical slugs
    for d in os.listdir(BASE):
        pdir = os.path.join(BASE, d)
        models_file = os.path.join(pdir, "models.md")
        if not os.path.isdir(pdir) or not os.path.exists(models_file):
            continue
        if d in ("models", "scripts") or d.startswith("."):
            continue

        with open(models_file) as f:
            content = f.read()

        changed = False
        new_lines = []
        for line in content.split("\n"):
            m = re.match(r'^(  - name: )(.+)', line)
            if m:
                entry = m.group(2).strip()
                # entry can be "slug" or "family/slug"
                slug = entry.split("/")[-1] if "/" in entry else entry
                if slug in to_remove and slug in slug_to_norm:
                    canon = slug_to_norm[slug]
                    if canon != slug:
                        canon_fam = family_of(canon)
                        canon_series = series_of(canon)
                        if canon_fam and canon_series:
                            new_lines.append(f"{m.group(1)}{canon_fam}/{canon_series}/{canon}")
                        elif canon_fam:
                            new_lines.append(f"{m.group(1)}{canon_fam}/{canon}")
                        else:
                            new_lines.append(f"{m.group(1)}{canon}")
                        changed = True
                        print(f"  {d}/models.md: {entry} → {canon_fam}/{canon_series}/{canon}")
                        continue
                elif slug in to_remove and slug not in slug_to_norm:
                    print(f"  WARNING: {d}/models.md: {slug} removed with no remap — dropping")
                    changed = True
                    continue
            new_lines.append(line)

        if changed:
            with open(models_file, "w") as f:
                f.write("\n".join(new_lines))

    print(f"\nDone! Removed {len(to_remove)} duplicate cards, updated provider refs")
    remaining = 0
    for root, dirs, files in os.walk(MODELS_DIR):
        remaining += len([f for f in files if f.endswith(".md")])
    print(f"Model cards remaining: {remaining}")


if __name__ == "__main__":
    main()
