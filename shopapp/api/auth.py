from __future__ import annotations

from functools import wraps
from typing import Callable, Optional, Tuple

from flask import Request, abort, g, request

from ..models import UserSession


def _extract_token(req: Request) -> Optional[str]:
    header = req.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    token = req.args.get("token")
    if token:
        return token.strip()
    return None


def resolve_user_session(token: str) -> Optional[UserSession]:
    if not token:
        return None
    session = UserSession.query.filter_by(session_token=token).first()
    if not session or session.revoked_at:
        return None
    return session


def token_required(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = _extract_token(request)
        session = resolve_user_session(token)
        if not session:
            abort(401, description="Invalid or missing token.")
        g.api_user = session.user
        g.api_session = session
        return fn(*args, **kwargs)

    return wrapper
