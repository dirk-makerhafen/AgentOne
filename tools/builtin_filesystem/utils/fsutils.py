import functools
import os
import time
from rapidfuzz.distance import Levenshtein
from itertools import combinations
import diff_match_patch as dmp_module
from collections import defaultdict
from pathlib import Path

@functools.lru_cache(maxsize=1000) 
def make_patch(from_content: str, to_content: str) -> str:
    dmp = dmp_module.diff_match_patch()
    diffs = dmp.diff_main(from_content, to_content)
    dmp.diff_cleanupSemantic(diffs)
    patches = dmp.patch_make(from_content, diffs)
    return dmp.patch_toText(patches)

@functools.lru_cache(maxsize=1000) 
def apply_patch(original_content, patching):
    dmp = dmp_module.diff_match_patch()
    patches = dmp.patch_fromText(patching)
    new_content, results = dmp.patch_apply(patches, original_content)
    return new_content

def get_abs_path(workingdir, path):
    if path.startswith("./"): path = path[2:]
    workingdir = os.path.expandvars(os.path.expanduser(workingdir))
    path = os.path.expandvars(os.path.expanduser(path))
    if not os.path.isabs(path):
        path = os.path.join(workingdir, path)
    return os.path.abspath(path)
    
def get_relative_path(workingdir, path):
    workingdir = os.path.expandvars(os.path.expanduser(workingdir))
    if workingdir.endswith("/"):
        workingdir = workingdir[:-1]
    path = os.path.expandvars(os.path.expanduser(path))
    if path[:2] == "./": path = path[1:]
    if path.startswith(workingdir):
        path = path[len(workingdir):]
        if len(path) > 0 and path[0] == '/':
            path = path[1:]
        if not path.startswith('./'):
            path = f"./{path}"
    if path == "": path = "./"
    return path

def clean_path(workingdir, path):
    abs_path = get_abs_path(workingdir, path)
    rel_path = get_relative_path(workingdir, abs_path)
    return abs_path, rel_path

def format_directory_listing(entries):
    """
    Format entries into an LLM-friendly flat hierarchy with explicit prefixes.
    
    Example:
    ./systems/management:
    d commands/
    
    ./systems/management/commands:
    f check_system_heartbeats.py
    """
    # Bucket files/dirs by parent directory
    dirs = defaultdict(list)
    for e in entries:
        path = Path(e["path"])
        parent = "./" + str(path.parent) if str(path.parent) != "." else "./"
        dirs[parent].append(e)

    # Sort directories and contents
    out = []
    for parent in sorted(dirs):
        out.append(f"{parent}:")
        for e in sorted(dirs[parent], key=lambda x: (0 if x["is_directory"] else 1, x["path"])):
            name = Path(e["path"]).name
            if e["is_directory"]:
                out.append(f"d {name}/")
            else:
                out.append(f"f {name}")
        out.append("")  # blank line between dirs

    return "\n".join(out).strip()

