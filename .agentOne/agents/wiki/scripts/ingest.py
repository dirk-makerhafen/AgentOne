
from __future__ import annotations
from datetime import datetime

from runtime.session.session import Session
from server.models.enums.message_enums import MessageContentType, MessagePartType
from server.models.enums.session_enums import SessionType
from server.models.message import Message


def ingest_next(_session: Session, limit=1) -> None:
    _, res = _session.get_tool("find_unlinked_raw").call(limit=limit)
    if res["items"]:
        results = []
        for item in res["items"]:
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
        session_type=SessionType.SUBSESSION,
    )
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

    verification_result = child_session.get_task("verify").delay(
        message=ingest_result_message, 
        path=path
    )

    final_result = child_session.get_task("ingest_verification_result").delay(
        verification_result=verification_result, 
    )

    return final_result


def verify(_session: Session, message:Message, path: str | None = None) -> None:
    msg = "".join( part.to_string() for part in message.parts.filter(type=MessagePartType.MESSAGE))
    return _session.get_tool("delegate_task").delay(prompt=f"The following item has been ingested by another agent: '{path}'\nResult: {msg}\n\nVerify that the ingestion was processed correctly. Correct errors.",blocking=True)


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