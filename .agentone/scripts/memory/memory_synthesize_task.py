"""Memory synthesis task for the task level."""

from __future__ import annotations

import importlib.util
import os

_common_path = os.path.join(os.path.dirname(__file__), "memory_synth_common.py")
_spec = importlib.util.spec_from_file_location("memory_synth_common", _common_path)
_common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_common)
run_synthesis = _common.run_synthesis

from runtime.session.session import Session


def memory_synthesize_task(
    _session: Session,
    item_id: str = "",
    memory_root: str = "",
    target_dir: str = "",
    sources: list = None,
    changed_files: list = None,
    **kwargs,
):
    if sources is None:
        sources = []
    if changed_files is None:
        changed_files = []
    return run_synthesis(
        _session,
        "task",
        item_id=item_id,
        memory_root=memory_root,
        target_dir=target_dir,
        sources=sources,
        changed_files=changed_files,
    )
