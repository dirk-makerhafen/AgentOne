from __future__ import annotations

import ast
import shlex
from dataclasses import dataclass, field
from typing import Any, Literal

from sh_guard import classify as sh_guard_classify


@dataclass
class GuardrailVerdict:
    action: Literal["allow", "ask", "deny"]
    score: int
    level: str
    reason: str
    risk_factors: list[str] = field(default_factory=list)


def check_shell_command(source: str, ask_threshold: int = 80) -> GuardrailVerdict:
    result = sh_guard_classify(source)
    score = result["score"]
    level = result["level"]
    quick = result.get("quick_decision", "safe")
    reason = result.get("reason", "")
    risk_factors = result.get("risk_factors", [])

    if quick == "blocked" or score >= ask_threshold:
        return GuardrailVerdict(
            action="ask",
            score=score,
            level=level,
            reason=reason,
            risk_factors=risk_factors,
        )
    else:
        return GuardrailVerdict(
            action="allow",
            score=score,
            level=level,
            reason="",
            risk_factors=[],
        )


def lint_shell_command(source: str) -> list[dict]:
    try:
        from pureshellcheck import check as sc_check

        findings = sc_check(source)
        return [
            {
                "line": f.line,
                "column": f.column,
                "code": f.code,
                "severity": f.severity,
                "message": f.message,
            }
            for f in findings
            if f.severity in ("error", "warning")
        ]
    except ImportError:
        return []


# ---------------------------------------------------------------------------
# Python guardrail — bandit-based (primary) + supplementary AST checks
# ---------------------------------------------------------------------------

# Bandit test ID → score overrides for findings whose severity doesn't match
# our desired guardrail strictness.
_BANDIT_OVERRIDES: dict[str, int] = {
    "B102": 95,  # exec used
    "B307": 95,  # eval / eval used
    "B201": 95,  # eval used (older ID)
    "B301": 85,  # pickle.load / loads
    "B302": 80,  # marshal.load / loads
    "B603": 85,  # subprocess call (LOW in bandit, elevated)
    "B605": 90,  # process with shell
    "B606": 90,  # process with shell (started with shell=True)
    "B607": 80,  # subprocess partial path
    "B113": 80,  # requests without timeout
    "B324": 20,  # weak MD5/SHA1 hash (crypto concern, not system safety)
    "B303": 20,  # md5 / sha1 (older ID, same reason)
}

# Bandit severity → base score (used when no override applies)
_BANDIT_SEVERITY_BASE: dict[str, int] = {
    "HIGH": 80,
    "MEDIUM": 60,
    "LOW": 35,
}

# Supplementary checks for patterns bandit does not detect.

_SUPPLEMENTARY_MODULES: dict[str, dict[str, int]] = {
    "socket": {"__any__": 80},
    "ctypes": {"__any__": 80},
    "os": {"remove": 85, "unlink": 85,
           "rmdir": 60, "removedirs": 85},
    "shutil": {"rmtree": 90},
}

_SUPPLEMENTARY_BUILTINS: dict[str, int] = {
    "compile": 50,
    "__import__": 85,
    "open": 35,
}


def _bandit_check(source: str) -> list[tuple[int, str]]:
    """Run bandit on *source* and return (score, reason) findings."""
    import tempfile
    import os as _os

    from bandit.core import config as _b_config
    from bandit.core import manager as _b_manager

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(source)
        tmp_path = f.name

    try:
        b_conf = _b_config.BanditConfig()
        b_mgr = _b_manager.BanditManager(b_conf, "file")
        b_mgr.discover_files([tmp_path])
        b_mgr.run_tests()
        results: list[tuple[int, str]] = []
        for issue in b_mgr.get_issue_list():
            score = _BANDIT_OVERRIDES.get(
                issue.test_id,
                _BANDIT_SEVERITY_BASE.get(issue.severity, 35),
            )
            results.append((score, f"[{issue.test_id}] {issue.text}"))
        return results
    finally:
        try:
            _os.unlink(tmp_path)
        except OSError:
            pass


def _extract_module_name(node: ast.Attribute) -> str:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    elif isinstance(current, ast.Call):
        return ""
    return ".".join(reversed(parts))


def _score_call_args_for_open(node: ast.Call) -> int:
    """Determine `open()` risk score based on its arguments."""
    mode = None

    for kw in node.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            mode = str(kw.value.value)
            break

    if mode is None and len(node.args) >= 2:
        second = node.args[1]
        if isinstance(second, ast.Constant):
            mode = str(second.value)

    if mode:
        if "w" in mode or "a" in mode or "+" in mode:
            return 85
        if "r" in mode:
            return 15

    return 15  # no explicit mode → default is 'r' (read)


def _supplementary_check(source: str, tree: ast.AST) -> list[tuple[int, str]]:
    """AST-based checks for patterns bandit does not detect."""
    imports: dict[str, str] = {}
    findings: list[tuple[int, str]] = []

    modules_sorted = sorted(
        _SUPPLEMENTARY_MODULES.items(),
        key=lambda x: len(x[0]),
        reverse=True,
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func

            # Direct name call — compile(), __import__(), open()
            if isinstance(func, ast.Name):
                name = func.id
                if name in _SUPPLEMENTARY_BUILTINS:
                    score = _SUPPLEMENTARY_BUILTINS[name]
                    if name == "open":
                        score = _score_call_args_for_open(node)
                    label = f"`{name}()`"
                    if score >= 80:
                        label = f"Built-in {label}"
                    findings.append((score, label))

                import_source = imports.get(name)
                if import_source:
                    for prefix, func_map in modules_sorted:
                        if import_source == prefix or import_source.startswith(prefix + "."):
                            attr = name
                            score = func_map.get(attr, func_map.get("__any__", 0))
                            if score:
                                findings.append((score, f"`{import_source}()`"))
                            break

            # Attribute call — socket.connect(), ctypes.CDLL(), os.remove()
            elif isinstance(func, ast.Attribute):
                module_name = _extract_module_name(func)
                if module_name:
                    for prefix, func_map in modules_sorted:
                        if module_name == prefix or module_name.startswith(prefix + "."):
                            attr = func.attr
                            score = func_map.get(attr, func_map.get("__any__", 0))
                            if score:
                                findings.append((score, f"`{module_name}.{attr}()`"))
                            break

        # Track imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports[alias.asname or alias.name] = alias.name

        if isinstance(node, ast.ImportFrom):
            if node.module:
                base = node.module
                for alias in node.names:
                    name = alias.asname or alias.name
                    imports[name] = f"{base}.{alias.name}"

    return findings


def check_python_command(source: str, ask_threshold: int = 80) -> GuardrailVerdict:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return GuardrailVerdict(
            action="allow",
            score=0,
            level="safe",
            reason="",
            risk_factors=["syntax_error"],
        )

    # Primary: bandit-based analysis
    all_findings: list[tuple[int, str]] = []
    try:
        all_findings.extend(_bandit_check(source))
    except ImportError:
        pass  # bandit not installed — rely on supplementary below

    # Supplementary: AST patterns bandit does not detect
    all_findings.extend(_supplementary_check(source, tree))

    if not all_findings:
        return GuardrailVerdict(
            action="allow",
            score=0,
            level="safe",
            reason="",
            risk_factors=[],
        )

    max_score = max(s for s, _ in all_findings)
    reasons = [r for _, r in all_findings if _ >= ask_threshold]

    if max_score >= 95:
        level = "critical"
    elif max_score >= 75:
        level = "danger"
    elif max_score >= 50:
        level = "caution"
    else:
        level = "safe"

    if max_score >= ask_threshold:
        return GuardrailVerdict(
            action="ask",
            score=max_score,
            level=level,
            reason="; ".join(reasons) if reasons else f"Python code (max score: {max_score})",
            risk_factors=[r.split("`")[1] if "`" in r else r for r in reasons],
        )

    return GuardrailVerdict(
        action="allow",
        score=max_score,
        level=level,
        reason="",
        risk_factors=[],
    )


# ---------------------------------------------------------------------------
# Filesystem-access (workspace policy) checks
#
# These complement the content-based scoring above.  Shell commands and
# Python code are parsed for filesystem *targets* (absolute paths, redirect
# targets, write-capable calls) and each target is evaluated against the
# session's workspace access policy.  A ``deny`` from the policy is final;
# an ``ask`` surfaces via the existing approval flow.
# ---------------------------------------------------------------------------

# Shell commands whose absolute operands are **read-only** (whitelist).
# Anything not listed here defaults to write-capable (fail-safe: unknown /
# exotic commands are treated as potentially writing, so novel writers are
# never silently missed).  In-place writers that *are* whitelisted are handled
# via ``_SHELL_WRITE_FLAGS``.
_SHELL_READ_COMMANDS: set[str] = {
    # display / pagination
    "cat", "head", "tail", "less", "more", "bat", "zcat", "bzcat",
    "zless", "zmore",
    # search
    "grep", "egrep", "fgrep", "rg", "ag", "ack", "ripgrep",
    # listing / metadata
    "ls", "dir", "vdir", "find", "which", "whereis", "type", "file",
    "stat", "wc", "du", "df", "tree", "realpath", "readlink",
    # text processing (read-only forms; write forms via _SHELL_WRITE_FLAGS)
    "sort", "uniq", "cut", "tr", "fmt", "fold", "nl", "column", "paste",
    "join", "rev", "tac", "strings", "od", "hexdump",
    # compare / checksums
    "diff", "cmp", "comm", "diff3", "md5sum", "sha1sum", "sha256sum",
    "sha384sum", "sha512sum", "shasum", "cksum", "sum",
    # env / info (no file writes)
    "echo", "printf", "env", "printenv", "pwd", "date", "whoami", "id",
    "hostname", "uname", "uptime", "who", "w", "last", "history", "cal",
    "nproc", "free", "ps", "getent", "host", "dig", "nslookup", "true",
    "false", "test",
}

# Commands that can write in place / to an output file even though they are
# whitelisted as read-only.  When one of these flags is seen, subsequent
# operands are treated as write targets.
_SHELL_WRITE_FLAGS: dict[str, set[str]] = {
    "sed": {"-i", "--in-place"},
    "sort": {"-o", "--output"},
    "perl": {"-i"},
}

# Explicitly write-capable commands.  A command is treated as write-capable if
# it is listed here OR simply not in ``_SHELL_READ_COMMANDS`` (fail-safe).
_SHELL_WRITE_COMMANDS: set[str] = {
    "cp", "mv", "rm", "rmdir", "mkdir", "touch", "ln", "tee",
    "install", "dd", "shred", "truncate", "mkfs", "chmod", "chown",
    "chgrp", "chattr", "setfacl", "tar", "zip", "unzip", "gzip", "gunzip",
    "bzip2", "bunzip2", "xz", "unxz", "zstd", "unzstd", "git", "pip",
    "pip3", "npm", "yarn", "make", "cmake", "curl", "wget", "scp",
    "rsync",
}


def _is_absolute_path(token: str) -> bool:
    """True if *token* looks like an absolute or ``~``-anchored path."""
    if not token:
        return False
    if token.startswith("~") or token.startswith("/"):
        return True
    return token.startswith("$HOME") or token.startswith("${HOME}")


def _is_device_node(token: str) -> bool:
    """True if *token* is a ``/dev/`` device node (not a filesystem path)."""
    return token.startswith("/dev/")


# pylint: disable=too-many-branches,too-many-statements
def _shell_targets(source: str) -> list[tuple[str, str]]:
    """Best-effort extraction of (path, action) targets from a shell command.

    Classification is **whitelist-based and fail-safe**:

    - A command not in ``_SHELL_READ_COMMANDS`` (i.e. anything unknown or
      explicitly a writer) is treated as write-capable, so its absolute
      operands are classified as ``write``.
    - Commands in the read whitelist classify their absolute operands as
      ``read``, unless an in-place write flag (``sed -i``, ``sort -o``,
      ``perl -i``) is seen, after which operands become ``write``.
    - Redirect targets (``>``/``>>``/``2>``) are always writes.
    - Relative paths are ignored — the shell runs with ``cwd`` set to the
      workspace root, so they cannot escape it (except via ``..``, a
      documented limitation).
    """
    targets: list[tuple[str, str]] = []
    try:
        tokens = shlex.split(source, posix=True)
    except ValueError:
        return targets

    prev_was_redirect = False
    current_cmd: str | None = None
    cmd_is_write = False
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        nxt = tokens[idx + 1] if idx + 1 < len(tokens) else ""
        idx += 1

        # Redirect operators (both spaced "> file" and glued ">file").
        if token in (">", ">>", "2>", "&>", "1>"):
            prev_was_redirect = True
            continue
        if token.startswith((">", "2>", "1>", "&>", ">>")):
            remainder = token.lstrip(">2&1")
            if not _is_device_node(remainder) and (
                remainder.startswith("/") or remainder.startswith("~")
                or remainder.startswith("$HOME")
            ):
                targets.append((remainder, "write"))
            prev_was_redirect = True
            continue
        if prev_was_redirect:
            if _is_absolute_path(token) and not _is_device_node(token):
                targets.append((token, "write"))
            prev_was_redirect = False
            continue

        # Separators start a new simple command.
        if token in (";", "&&", "||", "|"):
            current_cmd = None
            cmd_is_write = False
            continue

        if token == "cd":
            if _is_absolute_path(nxt):
                targets.append((nxt, "write"))
                idx += 1  # consume the target
            current_cmd = None
            cmd_is_write = False
            continue

        # First non-option bare word is the command name.
        if current_cmd is None and not token.startswith("-"):
            current_cmd = token
            # Fail-safe: explicit writers and any unknown command are treated
            # as write-capable.  Only known read-only commands classify their
            # operands as reads.
            cmd_is_write = (
                token in _SHELL_WRITE_COMMANDS
                or token not in _SHELL_READ_COMMANDS
            )
            continue

        # Options may flip a whitelisted read command into write mode
        # (sed -i, sort -o, perl -i).
        if token.startswith("-"):
            if current_cmd and current_cmd in _SHELL_WRITE_FLAGS:
                for flag in _SHELL_WRITE_FLAGS[current_cmd]:
                    if token == flag or token.startswith(flag):
                        cmd_is_write = True
                        break
            continue

        if _is_absolute_path(token):
            if _is_device_node(token):
                continue
            action = "write" if cmd_is_write else "read"
            targets.append((token, action))
    return targets


def check_shell_paths(source: str, policy: Any) -> GuardrailVerdict:
    """Evaluate filesystem targets in *source* against a workspace policy."""
    from runtime.workspace_access import evaluate  # pylint: disable=import-outside-toplevel

    verdicts = [evaluate(policy, path, action) for path, action in _shell_targets(source)]
    return _merge_path_verdicts(verdicts)


_PY_WRITE_ATTR_CALLS: dict[str, dict[str, int]] = {
    "os": {
        "remove": 90, "unlink": 90, "rmdir": 90, "removedirs": 90,
        "rename": 90, "replace": 90, "mkdir": 70, "makedirs": 70,
        "symlink": 85, "link": 85,
    },
    "shutil": {
        "rmtree": 95, "copy": 90, "copy2": 90, "move": 90,
        "copytree": 95,
    },
}


def _py_call_path(node: ast.Call) -> str | None:
    """Extract a constant string path argument from a call, if present."""
    for arg in node.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    for kw in node.keywords:
        if kw.arg in ("path", "src", "dst") and isinstance(kw.value, ast.Constant) \
                and isinstance(kw.value.value, str):
            return kw.value.value
    return None


def _py_open_mode(node: ast.Call) -> str | None:
    mode = None
    for kw in node.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            mode = str(kw.value.value)
            break
    if mode is None and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
        mode = str(node.args[1].value)
    return mode


# pylint: disable=too-many-nested-blocks
def _python_targets(source: str) -> list[tuple[str, str]]:
    """Extract (path, action) write targets from Python source via AST.

    Only *constant* path arguments are evaluated — dynamic paths fall back
    to the existing content-based scoring (documented limitation).
    """
    targets: list[tuple[str, str]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return targets

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func

        # open(...) with a write mode
        if isinstance(func, ast.Name) and func.id == "open":
            mode = _py_open_mode(node)
            if mode and ("w" in mode or "a" in mode or "+" in mode or "x" in mode):
                path = _py_call_path(node)
                if path:
                    targets.append((path, "write"))
            continue

        # os.* / shutil.* write calls
        if isinstance(func, ast.Attribute):
            module = _extract_module_name(func)
            if module:
                for prefix, func_map in _PY_WRITE_ATTR_CALLS.items():
                    if module == prefix or module.startswith(prefix + "."):
                        if func.attr in func_map:
                            path = _py_call_path(node)
                            if path:
                                targets.append((path, "write"))
                        break
    return targets


def check_python_paths(source: str, policy: Any) -> GuardrailVerdict:
    """Evaluate write targets in Python *source* against a workspace policy."""
    from runtime.workspace_access import evaluate  # pylint: disable=import-outside-toplevel

    verdicts = [
        evaluate(policy, path, action) for path, action in _python_targets(source)
    ]
    return _merge_path_verdicts(verdicts)


def _merge_path_verdicts(verdicts: list[GuardrailVerdict]) -> GuardrailVerdict:
    """Combine multiple path verdicts — ``deny`` wins, else ``ask``."""
    if not verdicts:
        return GuardrailVerdict(action="allow", score=0, level="safe", reason="")
    worst = verdicts[0]
    for verdict in verdicts:
        if verdict.action == "deny":
            return verdict
        if verdict.action == "ask" and worst.action != "deny":
            worst = verdict
    return worst
