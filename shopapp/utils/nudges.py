from __future__ import annotations

import json
from datetime import datetime, timedelta

from flask import current_app, url_for
from itsdangerous import URLSafeSerializer, BadSignature

from ..extensions import db
from ..models import Notification, User
from ..utils.whatsapp import send_whatsapp_message

TEMPLATES = {
    "STREAK_REMINDER": (
        "⚡ Quick win time!\n"
        "Keep your streak alive today. Open the app → do 1 action → +10 XP.\n"
        "{link}\n\n"
        "Opt-out: {opt_out}"
    ),
    "REFERRAL_NUDGE": (
        "🚀 Your friends want in.\n"
        "Share your link. When they activate, you both get +50 XP.\n"
        "{link}\n\n"
        "Opt-out: {opt_out}"
    ),
}

_SALT = "engagement-optout"


def _serializer() -> URLSafeSerializer:
    secret = current_app.config.get("SECRET_KEY")
    if not secret:
        raise RuntimeError("SECRET_KEY must be configured to generate opt-out links.")
    return URLSafeSerializer(secret_key=secret, salt=_SALT)


def build_opt_out_token(user_id: int) -> str:
    return _serializer().dumps({"user_id": user_id})


def resolve_opt_out_token(token: str) -> int | None:
    try:
        payload = _serializer().loads(token)
    except BadSignature:
        return None
    return payload.get("user_id")


def _has_recent_notification(user_id: int, template: str) -> bool:
    start = datetime.utcnow().date()
    today_start = datetime(start.year, start.month, start.day)
    tomorrow = today_start + timedelta(days=1)
    return (
        db.session.query(Notification.id)
        .filter(
            Notification.user_id == user_id,
            Notification.template == template,
            Notification.sent_at >= today_start,
            Notification.sent_at < tomorrow,
        )
        .count()
        > 0
    )


def _record_notification(user_id: int, template: str, payload: dict[str, object]) -> None:
    record = Notification(
        user_id=user_id,
        channel="whatsapp",
        template=template,
        payload=json.dumps(payload),
        sent_at=datetime.utcnow(),
    )
    db.session.add(record)
    db.session.commit()


def _send(user: User, template: str, link: str) -> bool:
    if not user or not user.phone:
        return False
    if getattr(user, "engagement_opt_out", False):
        return False
    if _has_recent_notification(user.id, template):
        return False

    token = build_opt_out_token(user.id)
    opt_out_link = url_for("engagement.opt_out", token=token, _external=True)
    message = TEMPLATES[template].format(link=link, opt_out=opt_out_link)

    if not send_whatsapp_message(user.phone, message):
        return False

    _record_notification(user.id, template, {"link": link})
    return True


def send_streak_reminder(user: User, link: str) -> bool:
    return _send(user, "STREAK_REMINDER", link)


def send_referral_nudge(user: User, link: str) -> bool:
    return _send(user, "REFERRAL_NUDGE", link)
