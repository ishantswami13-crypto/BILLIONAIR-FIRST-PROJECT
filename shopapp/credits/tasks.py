from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, Optional, Tuple

from flask import current_app

from ..extensions import db
from ..models import Credit, Customer
from ..utils.whatsapp import send_whatsapp_message

REMINDER_STATUSES = ('unpaid', 'adjusted')


def _normalise_phone(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    phone = ''.join(ch for ch in raw if ch.isdigit() or ch == '+')
    if not phone:
        return None
    if phone.startswith('+'):
        return phone
    default_cc = current_app.config.get('WHATSAPP_DEFAULT_COUNTRY_CODE', '+91')
    if not default_cc.startswith('+'):
        default_cc = f'+{default_cc}'
    return f'{default_cc}{phone.lstrip("0")}'


def _resolve_customer(credit: Credit) -> Optional[Customer]:
    if credit.customer_id:
        return Customer.query.get(credit.customer_id)
    if credit.customer_name:
        return Customer.query.filter(
            Customer.name.ilike(credit.customer_name)
        ).first()
    return None


def _resolve_phone(credit: Credit) -> Optional[str]:
    phone = credit.reminder_phone
    if not phone:
        customer = _resolve_customer(credit)
        phone = customer.phone if customer else None
    return _normalise_phone(phone)


def _message_for_credit(credit: Credit) -> str:
    shop_name = current_app.config.get('PRODUCT_NAME', 'ShopApp Store')
    amount = f'Rs {credit.total:,.2f}'
    date_str = credit.date.strftime('%d %b %Y')

    return (
        f"Hello {credit.customer_name or 'valued customer'},\n\n"
        f"This is a friendly reminder from {shop_name}. "
        f"Your udhar for {credit.item} ({amount}) from {date_str} is still pending.\n\n"
        "Please clear the dues at your earliest convenience. "
        "Reply to this message or reach out if you have already settled it.\n\n"
        f"Thank you!\n{shop_name}"
    )


def _eligible_credits(cutoff: datetime) -> Iterable[Credit]:
    return (
        Credit.query
        .filter(Credit.status.in_(REMINDER_STATUSES))
        .filter(Credit.reminder_opt_out.is_(False))
        .filter((Credit.last_reminder_at.is_(None)) | (Credit.last_reminder_at < cutoff))
        .order_by(Credit.date.asc())
        .all()
    )


def send_credit_reminder(credit: Credit) -> bool:
    phone = _resolve_phone(credit)
    if not phone:
        return False

    if send_whatsapp_message(phone, _message_for_credit(credit)):
        credit.last_reminder_at = datetime.utcnow()
        credit.reminder_count = (credit.reminder_count or 0) + 1
        credit.reminder_phone = phone
        db.session.commit()
        return True

    return False


def send_credit_reminders() -> Tuple[int, int]:
    """Send reminders for all eligible credits.

    Returns:
        success_count, failure_count
    """
    hours_between = current_app.config.get('WHATSAPP_REMINDER_COOLDOWN_HOURS', 24)
    cutoff = datetime.utcnow() - timedelta(hours=hours_between)
    credits = _eligible_credits(cutoff)

    sent = 0
    failed = 0
    for credit in credits:
        if send_credit_reminder(credit):
            sent += 1
        else:
            failed += 1
    return sent, failed
