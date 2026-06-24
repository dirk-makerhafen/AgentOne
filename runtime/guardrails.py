from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Literal

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

    all_findings: list[tuple[int, str]] = []

    # Primary: bandit-based analysis
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
