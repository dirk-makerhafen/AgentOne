
from __future__ import annotations
import re
from datetime import datetime
from runtime.session.session import Session
from server.models.enums.session_enums import SessionType

def _extract_date_from_path(rel_path: str) -> list:
    parts = rel_path.split("/")
    for i, p in enumerate(parts):
        if p.isdigit() and len(p) == 4 and 2000 <= int(p) <= 2030:
            mm = parts[i + 1] if i + 1 < len(parts) and parts[i + 1].isdigit() and 1 <= int(parts[i + 1]) <= 12 else None
            dd = parts[i + 2] if mm and i + 2 < len(parts) and parts[i + 2].isdigit() and 1 <= int(parts[i + 2]) <= 31 else None

            if not dd and mm and i + 2 < len(parts):
                # Raw archive folders are named YYYYMMDD-HHMM__sender__subject;
                # the day is the 7th-8th digit of the leading date stamp.
                day_m = re.match(r"^\d{4}\d{2}(\d{2})", parts[i + 2])
                if day_m and 1 <= int(day_m.group(1)) <= 31:
                    dd = day_m.group(1)
            if dd:
                return [p, mm, dd]
            if mm:
                return [p, mm, None]
            return [p, None, None]
    return[ None,None,None]

def ingest_next(_session: Session, limit:int=1):

    now = datetime.now().strftime("%Y%m%d.%H%M")
    ingest_session = _session.spawn_subagent(
        "wiki",
        name=f"{_session.name}:INGEST",
        description=f"Ingest session for parent session {_session.name}, pk:{_session.model.pk}",
        session_type=SessionType.SUBSESSION,
        group_key="wiki:ingest",
        disallowedToolNames=["+", "find_unlinked_raw"],
    )
    if ingest_session is None:
        return False, {"status": "error", "message": "Agent 'wiki' not found"}
    ingest_session.set_is_active(True)

    find_task = ingest_session.get_task("find_unlinked_raw")
    if find_task is None:
        return False, {"status": "error", "message": "task 'find_unlinked_raw' is not available"}
    success, data = find_task.call(limit=limit)
    if not success:
        return False, data if isinstance(data, dict) else {"status": "error", "message": str(data)}
    prev_res =  ingest_session.get_tool("todo_clear").delay()
    cnt = 0
    last_y,last_m,last_d = None,None,None
    if isinstance(data, dict) and data.get("items", None):
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
    if cnt == 0:
        return True, {"status": "success", "message": "no unlinked raw files found"}
    # The todo calls above only fill the queue; the child needs a turn to act
    # on it. The queue strategy parks this message until they have run.
    ingest_session.add_user_message(
        f"It is now {now}. Work through your todo list (todo_list) and ingest "
        f"each listed raw file, one at a time."
    )
    return True, {"status": "success", "message": f"{cnt} todo items created, ingest session started"}
