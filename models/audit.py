import json
from typing import Any, Optional


def write_audit_log(conn, *, user_id: Optional[int], action: str, entity: str, entity_id: Optional[int], details: Any):
    try:
        payload = json.dumps(details, ensure_ascii=False, default=str)
    except Exception:
        payload = json.dumps({"detail": str(details)}, ensure_ascii=False)

    conn.execute(
        """
        INSERT INTO audit_logs (user_id, action, entity, entity_id, details)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, action, entity, entity_id, payload),
    )

