from typing import List, Set, Any
from django.db.models import QuerySet

from runtime.session.session import Session

class HistoryLimiter:
    def __init__(self, session: Session, all_entries: List[Any]):
        self.session = session
        self.all_entries = all_entries
        
        # Load settings
        self.max_history_messages = self.session.max_history_messages

    def is_tool_call_limited(self, tool_call, message) -> bool:
        # Simplistic implementation for now
        # Could use HistoryLimit models later
        return False

    def is_general_message_limited(self, rule_name: str, entry) -> bool:
        # Check if we should add "TO_BE_FORGOTTEN" tag
        # Logic based on max_history_messages
        if self.max_history_messages > 0:
             # Find index of entry in all_entries (which is sorted newest first)
             try:
                 idx = self.all_entries.index(entry)
                 if idx >= self.max_history_messages:
                     return True
             except ValueError:
                 pass
        return False
