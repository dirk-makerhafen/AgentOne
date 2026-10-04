
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

            if not dd:
                dd_ = rel_path.split(f"/{p}{mm}",1)[-1].split("-")[0] 
                if dd_.isdigit() and len(dd_) == 2 and 1 <= int(dd_) <= 31:
                    dd = dd_
            if dd:
                return [p, mm, dd]
            if mm:
                return [p, mm, None]
            return [p, None, None]
    return[ None,None,None]

def ingest_next(_session: Session, limit:int=1):

    subagent_version = _session.get_subagent("wiki")
    if not subagent_version:
        return {"error": f"Agent 'wiki' not found"}

    now = datetime.now().strftime("%Y%m%d.%H%M")
    ingest_session_version = subagent_version.get_or_create_session(
        name=f"{_session.name}:INGEST",
        description=f"Ingest session for parent session {_session.name}, pk:{_session.model.pk}",
        workspace=_session.workspace,
        parent_session_version=_session.get_version_model(),
        session_type=SessionType.SUBSESSION,
    )
    # Fork inherits parent's session settings (auto_compact_max_tokens, api key, disallowed lists, etc.)
    parent_sv = _session.get_version_model()
    if parent_sv and parent_sv.session_settings:
        fork_settings = subagent_version.clone_settings(parent_sv.session_settings, disallowedToolNames=["+", "find_unlinked_raw"])
        ingest_session_version.session_settings = fork_settings
        SessionVersionModel.objects.filter(pk=ingest_session_version.pk).update(session_settings=fork_settings)
       
    ingest_session = Session(session_model=ingest_session_version.session, pinned_session_version=ingest_session_version)
    ingest_session.set_is_active(True)

    success, data = ingest_session.get_task("find_unlinked_raw").call(limit=limit)
    prev_res =  ingest_session.get_tool("todo_clear").delay()
    cnt = 0
    last_y,last_m,last_d = None,None,None
    if data.get("items", None):
        for item in data["items"]:
            p = item["file"]
            y,m,d = _extract_date_from_path(p)
            if last_d and d != last_d:
                prev_res = ingest_session.get_tool("todo_append").delay(text=f'Lint your work for {last_y}-{last_m}-{last_d}', prev_res=prev_res)
            if last_m and m != last_m:
                prev_res = ingest_session.get_tool("todo_append").delay(text=f'Lint your work for {last_y}-{last_m}', prev_res=prev_res)
            if last_y and y != last_y:
                prev_res = ingest_session.get_tool("todo_append").delay(text=f'Lint your work for {last_y}', prev_res=prev_res)
            
            last_y = y if y else last_y
            last_m = m if m else last_m
            last_d = d if d else last_d
            cnt += 1
            prev_res = ingest_session.get_tool("todo_append").delay(text=f'ingest: {item["file"]}', prev_res=prev_res)
    return True, f"{cnt} todo items created"
