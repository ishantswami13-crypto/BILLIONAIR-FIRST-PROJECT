from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Mapping

from flask import g

from ..extensions import db
from ..models import Event


def _normalize_user_id(explicit: int | None = None) -> int | None:
    if explicit is not None:
        return explicit
    if hasattr(g, "user_id") and g.user_id is not None:
        return g.user_id
    if hasattr(g, "user") and getattr(g, "user", None) is not None:
        user = g.user
        return getattr(user, "id", None)
    return None


def track(name: str, props: Mapping[str, Any] | None = None, user_id: int | None = None) -> None:
    """Persist a lightweight analytics event."""
    if not name:
        return

    payload: str
    try:
        payload = json.dumps(props or {})
    except (TypeError, ValueError):
        payload = "{}"

    event = Event(
        user_id=_normalize_user_id(user_id),
        name=name,
        props=payload,
        created_at=datetime.utcnow(),
    )
    db.session.add(event)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
