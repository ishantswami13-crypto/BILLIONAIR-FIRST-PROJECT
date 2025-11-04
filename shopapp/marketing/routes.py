from datetime import datetime

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for

from ..metrics import EVENTS
from ..models import User
from ..utils.track import track

marketing_bp = Blueprint("marketing", __name__)

FEATURES = [
    {
        "title": "Billing & Invoicing",
        "description": "Generate GST-ready invoices, share them instantly, and keep every sale reconciled.",
    },
    {
        "title": "Inventory Ground Control",
        "description": "Live stock dashboards with low-stock alerts so you never miss a reorder.",
    },
    {
        "title": "Automated Reports & Backups",
        "description": "Nightly email summaries and Drive backups keep leadership and auditors in sync.",
    },
]


@marketing_bp.route("/")
def home():
    if session.get("user"):
        return redirect(url_for("sales.index"))
    return redirect(url_for("auth.login"))


@marketing_bp.route("/landing")
@marketing_bp.route("/marketing")
def landing():
    if session.get("user"):
        return redirect(url_for("sales.index"))

    cfg = current_app.config
    payment_url = (
        cfg.get("PAYMENT_LINK")
        or cfg.get("STRIPE_CHECKOUT_URL")
        or cfg.get("RAZORPAY_PAYMENT_LINK")
    )

    waitlist_url = cfg.get("WAITLIST_URL")
    waitlist_embed = None
    if waitlist_url and "docs.google.com/forms" in waitlist_url:
        if "embedded=true" in waitlist_url:
            waitlist_embed = waitlist_url
        elif "viewform" in waitlist_url:
            waitlist_embed = waitlist_url.replace("viewform", "viewform?embedded=true")
        else:
            waitlist_embed = waitlist_url

    context = {
        "product_name": cfg.get("PRODUCT_NAME", "Evara SaaS"),
        "tagline": cfg.get("PRODUCT_TAGLINE", "Retail OS for high-velocity stores"),
        "demo_gif": cfg.get("DEMO_GIF_URL"),
        "payment_url": payment_url,
        "stripe_url": cfg.get("STRIPE_CHECKOUT_URL"),
        "razorpay_url": cfg.get("RAZORPAY_PAYMENT_LINK"),
        "waitlist_url": waitlist_url,
        "waitlist_embed": waitlist_embed,
        "features": FEATURES,
        "support_email": cfg.get("MAIL_SENDER") or "hello@example.com",
        "year": datetime.utcnow().year,
    }
    return render_template("marketing/landing.html", **context)


@marketing_bp.route("/nps", methods=["POST"])
def nps():
    if "user" not in session:
        flash("Sign in to rate your day.", "warning")
        return redirect(url_for("auth.login"))

    raw_score = request.form.get("score")
    try:
        score = int(raw_score)
    except (TypeError, ValueError):
        flash("Select a score between 0 and 10.", "warning")
        return redirect(request.referrer or url_for("engagement.hub"))

    score = max(0, min(10, score))
    user = User.query.filter_by(username=session.get("user")).first()
    track(EVENTS["NPS_SUBMITTED"], {"score": score}, user_id=user.id if user else None)
    flash("Thanks for the signal!", "success")
    return redirect(request.referrer or url_for("engagement.hub"))


@marketing_bp.route("/healthz")
def healthcheck():
    return jsonify({"status": "ok"})
