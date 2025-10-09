from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Setting, ShopProfile, Sale
from ..utils.audit import log_event
from ..utils.decorators import admin_required, login_required

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


def _branding_upload_dir() -> Path:
    root = Path(current_app.instance_path) / "branding"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _save_upload(file_storage, slug: str) -> str | None:
    if not file_storage or not file_storage.filename:
        return None

    filename = secure_filename(file_storage.filename)
    if not filename:
        return None

    dest = _branding_upload_dir() / f"{slug}_{filename}"
    file_storage.save(dest)
    return dest.relative_to(Path(current_app.root_path)).as_posix()


@settings_bp.route("/branding", methods=["GET", "POST"])
@login_required
@admin_required
def branding():
    profile = ShopProfile.query.get(1)
    if not profile:
        profile = ShopProfile(id=1)
        db.session.add(profile)
        db.session.commit()

    if request.method == "POST":
        profile.name = request.form.get("name") or profile.name
        profile.address = request.form.get("address") or profile.address
        profile.phone = request.form.get("phone") or profile.phone
        profile.gst = request.form.get("gst") or profile.gst
        profile.invoice_prefix = request.form.get("invoice_prefix") or profile.invoice_prefix
        profile.primary_color = request.form.get("primary_color") or profile.primary_color
        profile.secondary_color = request.form.get("secondary_color") or profile.secondary_color

        logo = request.files.get("logo")
        signature = request.files.get("signature")
        watermark = request.files.get("watermark")

        saved_logo = _save_upload(logo, "logo")
        saved_signature = _save_upload(signature, "signature")
        saved_watermark = _save_upload(watermark, "watermark")

        if saved_logo:
            profile.logo_path = saved_logo
        if saved_signature:
            profile.signature_path = saved_signature
        if saved_watermark:
            profile.watermark_path = saved_watermark

        db.session.commit()
        flash("Branding settings updated.", "success")
        return redirect(url_for("settings.branding"))

    sales_lock = Setting.query.filter_by(key="sales_lock_date").first()
    return render_template("settings/branding.html", profile=profile, sales_lock=sales_lock)


@settings_bp.route("/unlock-day", methods=["POST"])
@login_required
@admin_required
def unlock_day():
    Setting.query.filter_by(key="sales_lock_date").delete()
    Setting.query.filter_by(key="sales_lock_reason").delete()

    Sale.query.update({"locked": False})
    db.session.commit()
    log_event("unlock_day", resource_type="settings", resource_id=None, before=None, after={"action": "unlock"})
    flash("Sales lock cleared.", "success")
    return redirect(url_for("settings.branding"))
