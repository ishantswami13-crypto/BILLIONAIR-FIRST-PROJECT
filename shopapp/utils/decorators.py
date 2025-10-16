from functools import wraps

from flask import abort, redirect, session, url_for

from ..security import can_access as can_access_section, has_role, normalize_role


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("auth.login"))
        return fn(*args, **kwargs)

    return wrapper


def roles_required(*roles):
    normalized = {normalize_role(role) for role in roles}

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user" not in session:
                return redirect(url_for("auth.login"))
            if normalized and not has_role(*normalized):
                abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def admin_required(fn):
    return roles_required("owner")(fn)


def can_access(section: str) -> bool:
    return can_access_section(section)
