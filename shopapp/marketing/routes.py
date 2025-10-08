from datetime import datetime

from flask import Blueprint, current_app, jsonify, redirect, render_template, session, url_for

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
        "product_name": cfg.get("PRODUCT_NAME", "ShopApp SaaS"),
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


@marketing_bp.route("/healthz")
def healthcheck():
    return jsonify({"status": "ok"})
