from __future__ import annotations

from datetime import datetime

from sqlalchemy import func

from ..extensions import db
from ..models import Sale, Setting, ShopProfile

COUNTER_KEY = "invoice_counter"


def _get_prefix() -> str:
    profile = ShopProfile.query.get(1)
    return (profile.invoice_prefix or "INV") if profile else "INV"


def next_invoice_number() -> str:
    """Generate sequential invoice numbers (PREFIX-YYYYMMDD-#####)."""

    prefix = _get_prefix()
    today = datetime.utcnow().strftime("%Y%m%d")

    counter_setting = Setting.query.filter_by(key=COUNTER_KEY).with_for_update().first()
    if not counter_setting:
        counter_setting = Setting(key=COUNTER_KEY, value="0")
        db.session.add(counter_setting)
        db.session.flush()

    counter = int(counter_setting.value or "0") + 1
    counter_setting.value = str(counter)

    identifier = f"{prefix}-{today}-{counter:05d}"

    # Ensure uniqueness in case counter resets or migrations altered values.
    exists = db.session.query(func.count(Sale.id)).filter_by(invoice_number=identifier).scalar()
    if exists:
        counter += 1
        counter_setting.value = str(counter)
        identifier = f"{prefix}-{today}-{counter:05d}"

    return identifier
