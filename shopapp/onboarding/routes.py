from __future__ import annotations

from flask import Blueprint, redirect, render_template, request, session, url_for
import pytz

from ..extensions import db
from ..models import Item, ShopProfile

onboarding_bp = Blueprint("onboarding", __name__)


def _get_or_create_profile() -> ShopProfile:
    profile = ShopProfile.query.get(1)
    if profile is None:
        profile = ShopProfile(id=1, name="My Shop", shop_name="My Shop")
        db.session.add(profile)
        db.session.commit()
    return profile


@onboarding_bp.route("/onboarding/step1", methods=["GET", "POST"])
def onboarding_step1():
    if "user" not in session:
        return redirect(url_for("auth.login"))

    profile = _get_or_create_profile()
    timezones = [
        tz
        for tz in pytz.common_timezones
        if tz.startswith("Asia/") or tz in ("UTC", "Europe/London")
    ]
    error = None

    if request.method == "POST":
        shop_name = request.form.get("shop_name", "").strip()
        currency = request.form.get("currency", "INR").strip() or "INR"
        tz = request.form.get("timezone", "Asia/Kolkata").strip() or "Asia/Kolkata"
        gst_enabled = request.form.get("gst_enabled") == "on"

        if not shop_name:
            error = "Shop name is required."
        else:
            profile.shop_name = shop_name
            profile.name = shop_name
            profile.currency = currency
            profile.timezone = tz
            profile.gst_enabled = gst_enabled
            db.session.add(profile)
            db.session.commit()
            return redirect(url_for("onboarding.onboarding_step2"))

    return render_template(
        "onboarding/step1.html",
        profile=profile,
        timezones=timezones,
        error=error,
    )


@onboarding_bp.route("/onboarding/step2", methods=["GET", "POST"])
def onboarding_step2():
    if "user" not in session:
        return redirect(url_for("auth.login"))

    profile = _get_or_create_profile()
    error = None

    if request.method == "POST":
        items_csv = (request.form.get("items_csv") or "").strip()
        opening_raw = (request.form.get("opening_cash") or "").strip()
        low_raw = (request.form.get("low_stock_threshold") or "").strip()

        try:
            opening_cash = float(opening_raw) if opening_raw else 0.0
        except ValueError:
            error = "Opening cash must be a number."
            opening_cash = profile.opening_cash or 0.0

        try:
            low_stock_threshold = int(low_raw) if low_raw else 5
        except ValueError:
            error = "Low-stock threshold must be an integer."
            low_stock_threshold = profile.low_stock_threshold or 5

        if not error:
            profile.opening_cash = opening_cash
            profile.low_stock_threshold = low_stock_threshold
            db.session.add(profile)

            if items_csv:
                for line in items_csv.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    parts = [part.strip() for part in line.split(",", 2)]
                    if len(parts) != 3:
                        continue
                    name, price_raw, stock_raw = parts
                    if not name:
                        continue
                    try:
                        price = float(price_raw)
                        stock = int(stock_raw)
                    except ValueError:
                        continue
                    exists = Item.query.filter_by(name=name).first()
                    if exists:
                        continue
                    item = Item(name=name, price=price, current_stock=stock)
                    db.session.add(item)
            db.session.commit()
            return redirect(url_for("sales.index"))

    return render_template(
        "onboarding/step2.html",
        profile=profile,
        error=error,
        info=None,
    )
