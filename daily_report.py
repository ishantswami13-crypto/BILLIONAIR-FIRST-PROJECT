from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from flask import current_app
from sqlalchemy import func

from shopapp.extensions import db
from shopapp.models import Credit, Item, Sale, Setting
from shopapp.utils.audit import log_event
from shopapp.utils.mail import send_mail


def _format_currency(value: float) -> str:
    return f"Rs {value:,.2f}"


def generate_summary() -> Dict[str, Any]:
    today = datetime.utcnow().date()
    start = datetime(today.year, today.month, today.day)
    end = start + timedelta(days=1)

    revenue, discount, tax, count = (
        db.session.query(
            func.coalesce(func.sum(Sale.net_total), 0),
            func.coalesce(func.sum(Sale.discount), 0),
            func.coalesce(func.sum(Sale.tax), 0),
            func.count(Sale.id),
        )
        .filter(Sale.date >= start, Sale.date < end)
        .one()
    )

    best_item = (
        db.session.query(Sale.item, func.sum(Sale.quantity).label("qty"))
        .filter(Sale.date >= start, Sale.date < end)
        .group_by(Sale.item)
        .order_by(func.sum(Sale.quantity).desc())
        .first()
    )

    low_stock: List[Item] = (
        Item.query.filter(Item.current_stock <= func.coalesce(Item.reorder_level, 5))
        .order_by(Item.current_stock.asc())
        .limit(5)
        .all()
    )

    unpaid_credits: List[Credit] = (
        Credit.query.filter(Credit.status.in_(["unpaid", "adjusted"]))
        .order_by(Credit.date.desc())
        .all()
    )

    return {
        "date": today.isoformat(),
        "revenue": float(revenue or 0),
        "discount": float(discount or 0),
        "tax": float(tax or 0),
        "transactions": int(count or 0),
        "best_item": {"name": best_item[0], "quantity": int(best_item[1])} if best_item else None,
        "low_stock": [{"name": item.name, "qty": item.current_stock} for item in low_stock],
        "unpaid_credits": [
            {
                "customer": credit.customer_name,
                "item": credit.item,
                "quantity": credit.quantity,
                "total": float(credit.total or 0),
                "date": credit.date.strftime("%Y-%m-%d"),
            }
            for credit in unpaid_credits
        ],
    }


def build_email(summary: Dict[str, Any]) -> str:
    lines = [
        f"Daily Report - {summary['date']}",
        "",
        f"Total Sales: {summary['transactions']}",
        f"Total Revenue: {_format_currency(summary['revenue'])}",
        f"Total Tax: {_format_currency(summary['tax'])}",
    ]

    best = summary.get("best_item")
    if best:
        lines.append(f"Best-selling item: {best['name']} ({best['quantity']} sold)")
    lines.append("")

    lines.append("Low stock alerts:")
    if summary["low_stock"]:
        lines.extend([f"- {row['name']} -> only {row['qty']} left" for row in summary["low_stock"]])
    else:
        lines.append("- All items healthy.")

    lines.append("")
    lines.append("Outstanding credits:")
    if summary["unpaid_credits"]:
        for credit in summary["unpaid_credits"]:
            lines.append(
                f"- {credit['customer']} took {credit['quantity']} x {credit['item']} "
                f"({_format_currency(credit['total'])}) on {credit['date']}"
            )
    else:
        lines.append("- None.")

    return "\n".join(lines)


def lock_sales_for_today() -> None:
    now = datetime.utcnow()
    today = now.strftime("%Y-%m-%d")
    record = Setting.query.filter_by(key="sales_lock_date").first()
    previous_lock = record.value if record and record.value else None
    if not record:
        record = Setting(key="sales_lock_date", value=today)
        db.session.add(record)
    else:
        record.value = today

    auto_message = "Locked automatically after daily report."
    reason = Setting.query.filter_by(key="sales_lock_reason").first()
    if not reason:
        reason = Setting(key="sales_lock_reason", value=auto_message)
        db.session.add(reason)
    else:
        reason.value = auto_message

    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    locked_count = (
        Sale.query.filter(Sale.date >= start, Sale.date < end)
        .update({"locked": True}, synchronize_session=False)
        or 0
    )

    log_event(
        "sales_lock_auto",
        resource_type="sales",
        resource_id=None,
        before={"previous_lock": previous_lock},
        after={"locked_date": today, "locked_sales": int(locked_count)},
    )

    db.session.commit()


def send_daily_report() -> None:
    summary = generate_summary()
    body = build_email(summary)
    recipient = current_app.config.get("DAILY_REPORT_EMAIL") or current_app.config.get("DEFAULT_ADMIN_EMAIL")
    if not recipient:
        current_app.logger.warning(
            "Daily report email skipped: configure DAILY_REPORT_EMAIL or DEFAULT_ADMIN_EMAIL."
        )
        lock_sales_for_today()
        return

    subject = f"Daily Report – {summary['date']}"
    sent = send_mail(recipient, subject, body)
    if sent:
        current_app.logger.info("Daily report email sent to %s", recipient)
    else:
        current_app.logger.error("Daily report email failed to send to %s", recipient)
    lock_sales_for_today()
