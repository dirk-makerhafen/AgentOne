"""
Infer model parameters from model card slugs/names.

Many model names encode total and active parameter counts:
  - qwen3-235b-a22b     → total=235B, active=22B  (MoE)
  - baidu-ernie-4-5-vl-424b-a47b → total=424B, active=47B
  - llama-3-8b-instruct  → total=8B
  - distilbert-sst-2-int8 → total=67M (millions)

Usage:
    python3 scripts/infer_parameters.py          # dry-run: show what would change
    python3 scripts/infer_parameters.py --apply  # write inferred values to cards
"""

import os, re, sys
import yaml

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(BASE, "models")


def infer_from_slug(slug, existing_total=None, existing_active=None):
    """Infer (total_parameters, active_parameters) from a slug.

    Returns (total_B, active_B) where each is a float or None.
    Already-known values are returned as-is if non-zero.
    """
    if existing_total and existing_total > 0:
        return existing_total, existing_active

    # Find active params: pattern "a<digits>b" within slug
    total = None
    active = None

    am = re.search(r'a(\d+)b(?!\w)', slug)
    if am:
        active = float(am.group(1))

    # Find all <digits>b patterns and take the largest non-active one
    all_matches = list(re.finditer(r'(\d+)b(?!\w)', slug))
    candidates = []
    for m in all_matches:
        val = float(m.group(1))
        # Check if this is the active params match (preceded by 'a')
        start = m.start()
        if start > 0 and slug[start-1] == 'a' and active and val == active:
            continue  # this is the active params value
        candidates.append(val)

    if candidates:
        total = max(candidates)

    # If none found, try millions (e.g., "67m")
    if not total:
        mm = re.search(r'(\d+)m(?!\w)', slug)
        if mm:
            total = float(mm.group(1)) / 1000.0  # convert to billions

    return total, active


def main():
    apply_changes = "--apply" in sys.argv

    changed = 0
    for root, dirs, files in os.walk(MODELS_DIR):
        for fname in sorted(files):
            if not fname.endswith(".md"):
                continue
            path = os.path.join(root, fname)
            slug = fname[:-3]

            with open(path) as f:
                content = f.read()

            m = re.match(r'^---\n(.+?)\n---\n?(.*)', content, re.DOTALL)
            if not m:
                continue
            try:
                data = yaml.safe_load(m.group(1))
            except Exception:
                continue
            if not data:
                continue

            body = m.group(2)
            existing_total = data.get("total_parameters") or 0
            existing_active = data.get("active_parameters") or 0
            total, active = infer_from_slug(slug, existing_total, existing_active)

            if not total and not active:
                continue
            if total == existing_total and (active or 0) == existing_active:
                continue

            if not apply_changes:
                change_parts = []
                if total and total != existing_total:
                    change_parts.append(f"total={total}b")
                if active and active != existing_active:
                    change_parts.append(f"active={active}b")
                print(f"  {slug}: {', '.join(change_parts)}")
                changed += 1
                continue

            # Update frontmatter
            if total:
                data["total_parameters"] = total
            if active:
                data["active_parameters"] = active

            with open(path, "w") as f:
                f.write("---\n")
                f.write(yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False).rstrip())
                f.write("\n---\n")
                if body:
                    f.write(body.strip() + "\n")

            changes = []
            if total and total != existing_total:
                changes.append(f"total={total}b")
            if active and active != existing_active:
                changes.append(f"active={active}b")
            print(f"  {slug}: {', '.join(changes)}")
            changed += 1

    print(f"\nDone! {changed} cards would be updated" if not apply_changes else f"\nDone! Updated {changed} cards")
    if not apply_changes:
        print(f"Run with --apply to write changes")


if __name__ == "__main__":
    main()
