from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Credit
from ..utils.decorators import login_required
from .tasks import send_credit_reminder

credits_bp = Blueprint("credits", __name__, url_prefix="/credits")

OUTSTANDING_STATUSES = ("unpaid", "adjusted")


@credits_bp.route("/")
@login_required
def outstanding():
    rows = (
        Credit.query
        .filter(Credit.status.in_(OUTSTANDING_STATUSES))
        .order_by(Credit.date.asc())
        .all()
    )
    return render_template("credits/list.html", credits=rows)


@credits_bp.route("/<int:credit_id>/toggle", methods=["POST"])
@login_required
def toggle_opt_out(credit_id: int):
    credit = Credit.query.get_or_404(credit_id)
    credit.reminder_opt_out = not credit.reminder_opt_out
    db.session.commit()
    flash(
        f"Reminder opt-out {'enabled' if credit.reminder_opt_out else 'disabled'} for {credit.customer_name}.",
        "success",
    )
    return redirect(url_for("credits.outstanding"))


@credits_bp.route("/<int:credit_id>/send", methods=["POST"])
@login_required
def send_single_reminder(credit_id: int):
    credit = Credit.query.get_or_404(credit_id)
    if credit.reminder_opt_out:
        flash("Customer has opted out of reminders.", "warning")
        return redirect(url_for("credits.outstanding"))

    if send_credit_reminder(credit):
        flash("Reminder sent successfully.", "success")
    else:
        flash("Failed to send reminder — check phone configuration.", "danger")
    return redirect(url_for("credits.outstanding"))
