from runtime.agents.session import Session

def parse_user_message(session: Session, message :str, parts) -> list[dict]:
    if parts is None and message is not None:
        parts = [{"content": message, "type": "TEXT"}]
    if not parts:
        raise Exception("No message or message parts provided")
    return parts
