
from __future__ import annotations
from datetime import datetime
from runtime.session.session import Session
from server.models.enums.message_enums import MessageContentType, MessagePartType
from server.models.enums.session_enums import SessionType
from server.models.message import Message
from server.models.sessions.session_version import SessionVersionModel

def _extract_date_from_path(rel_path: str) -> list:
    parts = rel_path.split("/")
    for i, p in enumerate(parts):
        if p.isdigit() and len(p) == 4 and 2000 <= int(p) <= 2030:
            mm = parts[i + 1] if i + 1 < len(parts) and parts[i + 1].isdigit() and 1 <= int(parts[i + 1]) <= 12 else None
            dd = parts[i + 2] if mm and i + 2 < len(parts) and parts[i + 2].isdigit() and 1 <= int(parts[i + 2]) <= 31 else None
            if dd:
                return [p, mm, dd]
            if mm:
                return [p, mm, None]
            return [p, None, None]
    return None,None,None

def ingest_next(_session: Session, limit:int=1):
    _session.get_command("todo_clear").call(include_done=True)
    success, data = _session.get_task("find_unlinked_raw").call(limit=limit)
    cnt = 0
    last_y,last_m,last_d = None,None,None
    if data.get("items", None):
        for item in data["items"]:
            p = item["file"]
            y,m,d = _extract_date_from_path(p)
            if last_y and y != last_y:
                _session.get_command("todo_append").call(text=f'Lint your work for {last_y}')   
            if last_m and m != last_m:
                _session.get_command("todo_append").call(text=f'Lint your work for {last_y}-{last_m}')   
            if last_d and d != last_d:
                _session.get_command("todo_append").call(text=f'Lint your work for {last_y}-{last_m}-{last_d}')                    
            last_y = y if y else last_y
            last_m = m if m else last_m
            last_d = d if d else last_d
            cnt += 1
            _session.get_command("todo_append").call(text=f'ingest: {item["file"]}')
    return True, f"{cnt} todo items created"


def ingest_unlinked_raw_results(_session: Session, result: dict, **kwargs) -> str|list:
    success, data = result
    if data["items"]:
        results = []
        for item in data["items"]:
            results.append({
                "path": item["file"], 
                "result": _session.get_command("ingest_file").delay(path=item["file"])
            })
        return results
    return "No new raw files to ingest"


def ingest_file(_session: Session, path: str) -> None:
    """
    ingest message into the wiki

    Args:
        _session: The active agent session.
        path: Path of file to ingest

    Returns:
        Nothing
    """
    subagent_version = _session.get_subagent("wiki")
    if not subagent_version:
        return {"error": f"Agent 'wiki' not found"}

    now = datetime.now().strftime("%Y%m%d.%H%M")
    child_sv = subagent_version.get_or_create_session(
        name=f"wiki:ingest:{path}:{now}",
        description=f"Ingest session for {path}",
        workspace=_session.workspace,
        parent_session_version=_session.get_version_model(),
        session_type=SessionType.SUBTASK_DELEGATE,
    )
    # Fork inherits parent's session settings (auto_compact_limit, api key, disallowed lists, etc.)
    parent_sv = _session.get_version_model()
    if parent_sv and parent_sv.session_settings:
        fork_settings = subagent_version.clone_settings(parent_sv.session_settings, disallowedToolNames=["+", "find_unlinked_raw"])
        child_sv.session_settings = fork_settings
        SessionVersionModel.objects.filter(pk=child_sv.pk).update(session_settings=fork_settings)
       
    child_session = Session(session_model=child_sv.session, pinned_session_version=child_sv)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    working_dir = _session.workspace.path if _session.workspace else "unknown"
    ingest_result_message = child_session.get_task("ingest_user_message").delay(parts=[ 
        {
        "type": MessagePartType.MESSAGE, 
        "content_type": MessageContentType.TEXT, 
        "content": f"It is now {now}, your working dir is '{working_dir}'.\n"
        },
        {
        "type": MessagePartType.MESSAGE, 
        "content_type": MessageContentType.TEXT, 
        "content": f"Ingest '{path}'"
        },
    ])

    verification_result = child_session.get_task("verify").delay(message=ingest_result_message, path=path)

    final_result = child_session.get_task("ingest_verification_result").delay(verification_result=verification_result)

    return final_result


def verify(_session: Session, message:Message, path: str | None = None) -> None:
    msg = "".join( part.to_string() for part in message.parts.filter(type=MessagePartType.MESSAGE))
    return _session.get_tool("delegate_task").delay(prompt=f"The following item has been ingested by another agent: '{path}'\nResult: {msg}\n\nVerify that the ingestion was processed correctly. Correct errors if needed, dont ingest any new files, just double check the other agents work.",blocking=True)


def ingest_verification_result(_session: Session, verification_result:Message) -> None:
    msg = "".join( part.to_string() for part in verification_result.parts.filter(type=MessagePartType.MESSAGE))
    final_result = _session.get_task("ingest_user_message").delay(parts=[{
            "type": MessagePartType.MESSAGE, 
            "content_type": MessageContentType.TEXT, 
            "content": f"An external agent did a verification run of your last operation, here is its result:\n"
        },
        {
            "type": MessagePartType.MESSAGE, 
            "content_type": MessageContentType.TEXT, 
            "content": msg
        },
        {
            "type": MessagePartType.MESSAGE, 
            "content_type": MessageContentType.TEXT, 
            "content": "If you are happy with the result and everything has been commited to git, call final_result to finish this ingestion."
        },
    ])
    return final_result