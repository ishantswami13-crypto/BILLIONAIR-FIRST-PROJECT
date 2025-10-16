from __future__ import annotations

from flask import session

from .models import UserRole

ROLES = ("owner", "cashier", "accountant")
DEFAULT_ROLE = "owner"

ROLE_PERMISSIONS = {
    "owner": {"all"},
    "cashier": {"dashboard", "inventory", "customers", "credits"},
    "accountant": {"reports", "credits", "assistant"},
}


def _as_value(role: str | UserRole | None) -> str | None:
    if isinstance(role, UserRole):
        return role.value
    return role


def normalize_role(role: str | UserRole | None) -> str:
    if not role:
        return DEFAULT_ROLE
    role = _as_value(role)
    if not role:
        return DEFAULT_ROLE
    role = role.lower()
    if role == "admin":
        return "owner"
    if role not in ROLES:
        return DEFAULT_ROLE
    return role


def get_current_role() -> str:
    return normalize_role(session.get("role"))


def has_role(*roles: str) -> bool:
    current = get_current_role()
    normalized = {normalize_role(role) for role in roles} or {current}
    return current in normalized


def can_access(section: str) -> bool:
    current = get_current_role()
    allowed = ROLE_PERMISSIONS.get(current, ROLE_PERMISSIONS[DEFAULT_ROLE])
    return "all" in allowed or section in allowed
