"""
Simple liveness check command. Responds with agent/session info.
"""

from __future__ import annotations

from runtime.session.session import Session


from collections import Counter, defaultdict

def ocr(session: Session, image_data: str | None = None, allow_cloud=False, ):
    pass