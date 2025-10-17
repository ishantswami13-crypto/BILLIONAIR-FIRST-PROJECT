from datetime import datetime, timedelta

from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import func

from ..extensions import db
from ..models import Credit, Customer, Item
from ..utils.decorators import login_required
from .tasks import send_credit_reminder, send_credit_reminders

credits_bp = Blueprint("credits", __name__, url_prefix="/credits")

OUTSTANDING_STATUSES = ("unpaid", "adjusted")


@credits_bp.route("/")
@login_required
def list_credits():
    outstanding = (
        Credit.query
        .filter(Credit.status.in_(OUTSTANDING_STATUSES))
        .order_by(Credit.date.desc())
        .all()
    )

    total_unpaid = round(sum(float(credit.total or 0) for credit in outstanding), 2)
    unpaid_count = len(outstanding)

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    reminders_30d = (
        Credit.query
        .filter(Credit.last_reminder_at.isnot(None))
        .filter(Credit.last_reminder_at >= thirty_days_ago)
        .count()
    )

    week_ago = datetime.utcnow() - timedelta(days=7)
    paid_week = (
        db.session.query(func.coalesce(func.sum(Credit.total), 0))
        .filter(Credit.status == "paid")
        .filter(Credit.date >= week_ago)
        .scalar() or 0.0
    )

    credits_data = [
        {
            "id": credit.id,
            "date": credit.date.strftime("%Y-%m-%d") if credit.date else "",
            "customer": credit.customer.name if credit.customer else (credit.customer_name or "Walk-in"),
            "item": credit.item,
            "quantity": int(credit.quantity or 0),
            "total": float(credit.total or 0),
            "status": credit.status,
            "last_reminder": credit.last_reminder_at.strftime("%Y-%m-%d") if credit.last_reminder_at else None,
        }
        for credit in outstanding
    ]

    return render_template(
        "credits/list.html",
        credits=credits_data,
        total_unpaid=total_unpaid,
        unpaid_count=unpaid_count,
        reminders_30d=reminders_30d,
        paid_week=round(float(paid_week), 2),
    )


@credits_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        try:
            customer_id = int(request.form.get("customer_id", 0))
            item_id = int(request.form.get("item_id", 0))
            quantity = int(request.form.get("quantity") or 1)
        except (TypeError, ValueError):
            flash("Enter valid details.", "warning")
            return redirect(url_for("credits.new"))

        customer = Customer.query.get(customer_id)
        item = Item.query.get(item_id)
        if not customer or not item:
            flash("Select a valid customer and item.", "warning")
            return redirect(url_for("credits.new"))

        total = float(item.price or 0) * quantity
        credit = Credit(
            customer_id=customer.id,
            customer_name=customer.name,
            item=item.name,
            quantity=quantity,
            total=total,
            status="unpaid",
            reminder_phone=customer.phone,
        )
        db.session.add(credit)
        db.session.commit()
        flash("Credit entry added.", "success")
        return redirect(url_for("credits.list_credits"))

    customers = Customer.query.order_by(Customer.name.asc()).all()
    items = Item.query.order_by(Item.name.asc()).all()
    return render_template("credits/new.html", customers=customers, items=items)


@credits_bp.route("/send-all", methods=["POST"])
@login_required
def send_reminders():
    sent, failed = send_credit_reminders()
    message = f"Sent {sent} reminder(s)."
    if failed:
        message += f" {failed} reminder(s) failed."
        flash(message, "warning")
    else:
        flash(message, "success")
    return redirect(url_for("credits.list_credits"))


@credits_bp.route("/<int:credit_id>/send", methods=["POST"])
@login_required
def send_one(credit_id: int):
    credit = Credit.query.get_or_404(credit_id)
    if credit.reminder_opt_out:
        flash("Customer has opted out of reminders.", "warning")
        return redirect(url_for("credits.list_credits"))

    if send_credit_reminder(credit):
        flash("Reminder sent successfully.", "success")
    else:
        flash("Failed to send reminder - check phone configuration.", "danger")
    return redirect(url_for("credits.list_credits"))


@credits_bp.route("/<int:credit_id>/mark-paid", methods=["POST"])
@login_required
def pay(credit_id: int):
    credit = Credit.query.get_or_404(credit_id)
    credit.status = "paid"
    db.session.commit()
    flash(f"Marked credit #{credit.id} as paid.", "success")
    return redirect(url_for("credits.list_credits"))
