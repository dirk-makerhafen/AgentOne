"""Shared helpers for memory synthesis tasks."""

from __future__ import annotations

from pathlib import Path

from server.models.agents.agent import AgentModel
from runtime.session.session import Session


PROMPT_FILES = {
    "task": "prompts/task.md",
    "agent": "prompts/agent.md",
    "scope": "prompts/scope.md",
}


def run_synthesis(_session: Session, level: str, item_id: str, memory_root: str,
                  target_dir: str, sources: list, changed_files: list,
                  timeout: int = 300) -> tuple[bool, dict]:
    try:
        agent = AgentModel.objects.get(name="memory-manage")
    except AgentModel.DoesNotExist:
        return False, {"error": "memory-manage agent not found"}
    av = agent.latest_agent_version
    if av is None:
        return False, {"error": "memory-manage has no version"}

    sv = av.get_or_create_session(
        name=f"memory:{level}:{int(__import__('time').time())}",
        workspace=_session.workspace if hasattr(_session, "workspace") else None,
        session_type="subsession",
        group_key=f"memory:{level}",
    )
    session = Session(session_model=sv.session, pinned_session_version=sv)

    prompt_path = Path(__file__).resolve().parent / PROMPT_FILES[level]
    prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
    prompt += "\n\nTarget directory: " + str(target_dir) + "\n"
    prompt += "Source files:\n" + "\n".join(str(s) for s in (sources or [])) + "\n"
    prompt += "Changed files since last run:\n" + "\n".join(str(c) for c in (changed_files or [])) + "\n"
    prompt += f"item_id: {item_id}\nmemory_root: {memory_root}\n"
    prompt += "\nAfter writing memory.md and reflection.md, call memory_collect_results(item_id=..., memory_root=..., result=<summary>) then final_result."

    call = session.add_user_message(prompt)
    # wait for completion
    try:
        res = call.get_result(timeout=timeout)
    except Exception as e:  # pylint: disable=broad-exception-caught
        res = None
        err = str(e)
    else:
        err = ""

    # best-effort collect_results
    try:
        collect = _session.get_tool("memory_collect_results")
        if collect is not None:
            collect.apply_async(kwargs={
                "item_id": item_id,
                "memory_root": memory_root,
                "result": str(res)[:500] if res is not None else err,
            })
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    return True, {"level": level, "item_id": item_id, "result": str(res)[:200] if res is not None else err}
