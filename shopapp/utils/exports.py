from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import AuditLog, Credit, Expense, Item, Sale
from ..reports.routes import build_summary
from ..utils.pdfs import create_zreport_pdf


ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _clamp_days(raw: int) -> int:
    return max(7, min(raw, 365))


def build_audit_log_csv(entries: Iterable[AuditLog]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "timestamp_utc",
            "user",
            "action",
            "resource_type",
            "resource_id",
            "ip_address",
            "user_agent",
            "details",
            "before_state",
            "after_state",
        ]
    )
    for entry in entries:
        writer.writerow(
            [
                entry.ts.strftime(ISO_FORMAT) if entry.ts else "",
                entry.user or "system",
                entry.action or "",
                entry.resource_type or "",
                entry.resource_id or "",
                entry.ip_address or "",
                entry.user_agent or "",
                entry.details or "",
                entry.before_state or "",
                entry.after_state or "",
            ]
        )
    return buffer.getvalue()


def _sales_csv(start: datetime, end: datetime) -> str:
    query = (
        Sale.query.options(joinedload(Sale.customer))
        .filter(Sale.date >= start, Sale.date < end)
        .order_by(Sale.date.asc(), Sale.id.asc())
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "datetime_utc",
            "invoice_number",
            "item",
            "quantity",
            "amount_net",
            "tax",
            "discount",
            "payment_method",
            "customer_name",
            "customer_id",
            "locked",
        ]
    )
    for sale in query.all():
        customer = getattr(sale, "customer", None)
        writer.writerow(
            [
                sale.id,
                sale.date.strftime(ISO_FORMAT) if sale.date else "",
                sale.invoice_number or "",
                sale.item,
                sale.quantity,
                f"{sale.net_total:.2f}",
                f"{sale.tax:.2f}",
                f"{sale.discount:.2f}",
                sale.payment_method or "cash",
                customer.name if customer else "",
                customer.id if customer else "",
                "yes" if sale.locked else "no",
            ]
        )
    return buffer.getvalue()


def _expenses_csv(start: datetime, end: datetime) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "date", "category", "amount", "notes"])
    rows = (
        Expense.query.filter(Expense.date >= start.date(), Expense.date <= (end - timedelta(seconds=1)).date())
        .order_by(Expense.date.asc(), Expense.id.asc())
        .all()
    )
    for expense in rows:
        writer.writerow(
            [
                expense.id,
                expense.date.isoformat() if expense.date else "",
                expense.category or (expense.category_rel.name if expense.category_rel else ""),
                f"{(expense.amount or 0):.2f}",
                (expense.notes or "").replace("\n", " ").strip(),
            ]
        )
    return buffer.getvalue()


def _credits_csv() -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "customer_id", "customer_name", "item", "quantity", "total", "status", "date"])
    rows = (
        Credit.query.filter(Credit.status.in_(["unpaid", "adjusted"]))
        .order_by(Credit.date.desc(), Credit.id.desc())
        .all()
    )
    for credit in rows:
        writer.writerow(
            [
                credit.id,
                credit.customer_id or "",
                credit.customer_name or "",
                credit.item or "",
                credit.quantity or "",
                f"{(credit.total or 0):.2f}",
                credit.status or "",
                credit.date.strftime(ISO_FORMAT) if credit.date else "",
            ]
        )
    return buffer.getvalue()


def _inventory_csv() -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "name", "stock", "reorder_level", "price", "gst_rate", "barcode", "hsn"])
    for item in Item.query.order_by(Item.name.asc()).all():
        writer.writerow(
            [
                item.id,
                item.name,
                item.current_stock,
                item.reorder_level,
                f"{(item.price or 0):.2f}",
                item.gst_rate or 0,
                item.barcode or "",
                item.hsn or "",
            ]
        )
    return buffer.getvalue()


def generate_ca_bundle(days: int = 30) -> tuple[bytes, str]:
    window_days = _clamp_days(days)
    end = datetime.utcnow().replace(microsecond=0)
    start = end - timedelta(days=window_days)

    audit_rows = (
        AuditLog.query.filter(AuditLog.ts >= start)
        .order_by(AuditLog.ts.asc())
        .all()
    )

    audit_csv = build_audit_log_csv(audit_rows)
    sales_csv = _sales_csv(start, end)
    expenses_csv = _expenses_csv(start, end)
    credits_csv = _credits_csv()
    inventory_csv = _inventory_csv()

    summary = build_summary(end.strftime("%Y-%m-%d"))
    zreport_path = create_zreport_pdf(summary)
    with open(zreport_path, "rb") as handle:
        zreport_bytes = handle.read()
    Path(zreport_path).unlink(missing_ok=True)

    manifest = {
        "generated_at": end.strftime(ISO_FORMAT),
        "window_start": start.strftime(ISO_FORMAT),
        "window_end": end.strftime(ISO_FORMAT),
        "days_requested": days,
        "days_included": window_days,
        "entries": {
            "audit_log": len(audit_rows),
            "sales": SalesCountQuery.count(start, end),
            "expenses": ExpensesCountQuery.count(start, end),
            "credits": CreditsCountQuery.count(),
            "inventory": Item.query.count(),
        },
    }

    bundle = io.BytesIO()
    with ZipFile(bundle, "w", ZIP_DEFLATED) as archive:
        archive.writestr("logs/audit_log.csv", audit_csv.encode("utf-8"))
        archive.writestr(f"sales/sales_{start:%Y%m%d}_{end:%Y%m%d}.csv", sales_csv.encode("utf-8"))
        archive.writestr(f"expenses/expenses_{start:%Y%m%d}_{end:%Y%m%d}.csv", expenses_csv.encode("utf-8"))
        archive.writestr("credits/outstanding_credits.csv", credits_csv.encode("utf-8"))
        archive.writestr("inventory/items_snapshot.csv", inventory_csv.encode("utf-8"))
        archive.writestr(f"reports/zreport_{summary['date']}.pdf", zreport_bytes)
        archive.writestr("manifest.json", json.dumps(manifest, indent=2).encode("utf-8"))

    bundle.seek(0)
    filename = f"evara_ca_bundle_{end:%Y%m%d_%H%M%S}.zip"
    return bundle.getvalue(), filename


class SalesCountQuery:
    @staticmethod
    def count(start: datetime, end: datetime) -> int:
        return (
            db.session.query(Sale.id)
            .filter(Sale.date >= start, Sale.date < end)
            .count()
        )


class ExpensesCountQuery:
    @staticmethod
    def count(start: datetime, end: datetime) -> int:
        return (
            db.session.query(Expense.id)
            .filter(Expense.date >= start.date(), Expense.date <= (end - timedelta(seconds=1)).date())
            .count()
        )


class CreditsCountQuery:
    @staticmethod
    def count() -> int:
        return (
            Credit.query.filter(Credit.status.in_(["unpaid", "adjusted"])).count()
        )
