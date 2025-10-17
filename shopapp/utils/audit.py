from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from flask import has_request_context, request, session

from ..extensions import db
from ..models import AuditLog


def log_event(action: str, resource_type: str | None = None, resource_id: int | None = None,
              before: Any | None = None, after: Any | None = None) -> None:
    if has_request_context():
        actor = session.get("user")
        ip_address = request.remote_addr
        user_agent = request.headers.get("User-Agent")
    else:
        actor = "system"
        ip_address = None
        user_agent = None

    entry = AuditLog(
        ts=datetime.utcnow(),
        user=actor,
        action=action,
        details=json.dumps({"resource": resource_type, "id": resource_id}),
        resource_type=resource_type,
        resource_id=resource_id,
        before_state=json.dumps(before, default=str) if before is not None else None,
        after_state=json.dumps(after, default=str) if after is not None else None,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.session.add(entry)
