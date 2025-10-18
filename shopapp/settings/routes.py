from __future__ import annotations

from datetime import datetime, timedelta
import secrets
import json
from pathlib import Path

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import (
    ApiWebhook,
    Event,
    Plan,
    Referral,
    Setting,
    ShopProfile,
    Sale,
    User,
    UserInvite,
    UserQuest,
    UserRole,
    UserSession,
    WebhookEvent,
)
from ..utils.audit import log_event
from ..utils.decorators import admin_required, login_required
from ..utils.qr import qr_to_base64

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


@settings_bp.route("/")
@login_required
@admin_required
def overview():
    profile = ShopProfile.query.get(1)
    active_plan = None
    if profile and profile.plan_id:
        active_plan = Plan.query.get(profile.plan_id)
    elif profile and profile.plan_slug:
        active_plan = Plan.query.filter_by(slug=profile.plan_slug).first()

    sections = [
        {
            "title": "Branding",
            "description": "Update store details, theme, and invoice visuals.",
            "endpoint": "settings.branding",
        },
        {
            "title": "Team & Access",
            "description": "Invite teammates, assign roles, and manage sessions.",
            "endpoint": "settings.access_dashboard",
        },
        {
            "title": "Apps & Webhooks",
            "description": "Connect integrations, manage API keys, and watch webhooks.",
            "endpoint": "settings.connect",
        },
    ]

    return render_template(
        "settings/index.html",
        profile=profile,
        active_plan=active_plan,
        sections=sections,
    )


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

        theme_choice = (request.form.get("ui_theme") or "mint").strip().lower()
        if theme_choice not in {"mint", "purple"}:
            theme_choice = "mint"
        theme_setting = Setting.query.filter_by(key="ui_theme").first()
        if theme_setting:
            theme_setting.value = theme_choice
        else:
            db.session.add(Setting(key="ui_theme", value=theme_choice))

        db.session.commit()
        flash("Branding settings updated.", "success")
        return redirect(url_for("settings.branding"))

    sales_lock = Setting.query.filter_by(key="sales_lock_date").first()
    lock_reason = Setting.query.filter_by(key="sales_lock_reason").first()
    theme_setting = Setting.query.filter_by(key="ui_theme").first()
    current_theme = (theme_setting.value if theme_setting and theme_setting.value else "mint").strip().lower()
    if current_theme not in {"mint", "purple"}:
        current_theme = "mint"
    return render_template(
        "settings/branding.html",
        profile=profile,
        sales_lock=sales_lock,
        lock_reason=lock_reason,
        current_theme=current_theme,
    )


@settings_bp.route("/unlock-day", methods=["POST"])
@login_required
@admin_required
def unlock_day():
    reason = (request.form.get("reason") or "").strip()
    if not reason:
        flash("Add a short reason before unlocking the books.", "warning")
        return redirect(url_for("settings.branding"))

    lock_setting = Setting.query.filter_by(key="sales_lock_date").first()
    previous_lock = lock_setting.value if lock_setting and lock_setting.value else None
    if lock_setting:
        db.session.delete(lock_setting)

    unlocked_total = (
        Sale.query.update({"locked": False}, synchronize_session=False) or 0
    )
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    actor = session.get("user") or "system"
    message = f"Unlocked manually on {timestamp} by {actor}: {reason} ({int(unlocked_total)} sales reset)"
    lock_reason = Setting.query.filter_by(key="sales_lock_reason").first()
    if not lock_reason:
        lock_reason = Setting(key="sales_lock_reason", value=message)
        db.session.add(lock_reason)
    else:
        lock_reason.value = message

    log_event(
        "unlock_day",
        resource_type="settings",
        resource_id=None,
        before={"locked_date": previous_lock},
        after={
            "action": "unlock",
            "reason": reason,
            "unlocked_sales": int(unlocked_total),
        },
    )
    db.session.commit()
    flash("Sales lock cleared. Override reason recorded.", "success")
    return redirect(url_for("settings.branding"))


def _ensure_base_plan(profile: ShopProfile | None) -> None:
    if not profile or not profile.plan_slug:
        return
    if profile.plan_id:
        return
    base_plan = Plan.query.filter_by(slug=profile.plan_slug).first()
    if base_plan:
        profile.plan_id = base_plan.id


def _current_user() -> User | None:
    username = session.get("user")
    if not username:
        return None
    return User.query.filter_by(username=username).first()


def _connect_context(qr_preview: dict[str, str] | None = None) -> dict[str, object]:
    sample_endpoint = url_for(
        "webhooks.ingest_webhook",
        provider="razorpay",
        event="payment.completed",
        _external=True,
    )
    pending_count = (
        WebhookEvent.query.filter(WebhookEvent.status != "matched").count()
    )
    webhooks = (
        ApiWebhook.query.order_by(ApiWebhook.provider.asc(), ApiWebhook.event.asc()).all()
    )
    events = (
        WebhookEvent.query.order_by(WebhookEvent.created_at.desc()).limit(50).all()
    )

    sale_ids = {event.matched_sale_id for event in events if event.matched_sale_id}
    sale_map: dict[int, Sale] = {}
    if sale_ids:
        sale_map = {
            sale.id: sale
            for sale in Sale.query.filter(Sale.id.in_(sale_ids)).all()
        }

    decorated_events = []
    for entry in events:
        payload_data: dict[str, object] = {}
        if entry.payload:
            try:
                parsed = json.loads(entry.payload)
                if isinstance(parsed, dict):
                    payload_data = parsed
            except (ValueError, TypeError):
                payload_data = {}

        summary = {
            "reference": payload_data.get("reference")
            or payload_data.get("invoice_number")
            or payload_data.get("order_id")
            or payload_data.get("txn_reference"),
            "amount": None,
            "currency": payload_data.get("currency")
            or payload_data.get("currency_code")
            or payload_data.get("currencySymbol"),
        }

        for key in ("amount", "total", "value", "gross_amount"):
            raw = payload_data.get(key)
            if raw is None:
                continue
            try:
                summary["amount"] = float(raw)
            except (TypeError, ValueError):
                try:
                    summary["amount"] = float(str(raw).replace(",", "").strip())
                except (TypeError, ValueError):
                    summary["amount"] = None
            break

        decorated_events.append(
            {
                "id": entry.id,
                "created_at": entry.created_at,
                "provider": entry.webhook.provider if entry.webhook else None,
                "event": entry.webhook.event if entry.webhook else None,
                "status": entry.status,
                "last_error": entry.last_error,
                "external_id": entry.external_id,
                "summary": summary,
                "matched_sale": sale_map.get(entry.matched_sale_id),
            }
        )

    return {
        "sample_endpoint": sample_endpoint,
        "pending_count": pending_count,
        "webhooks": webhooks,
        "events": decorated_events,
        "qr_preview": qr_preview,
    }


@settings_bp.route("/access")
@login_required
@admin_required
def access_dashboard():
    users = User.query.order_by(User.username.asc()).all()
    invites = UserInvite.query.order_by(UserInvite.created_at.desc()).all()
    sessions = (
        UserSession.query.filter(UserSession.revoked_at.is_(None))
        .order_by(UserSession.created_at.desc())
        .all()
    )
    return render_template(
        "settings/access.html",
        users=users,
        invites=invites,
        sessions=sessions,
        roles=list(UserRole),
    )


@settings_bp.route("/access/invite", methods=["POST"])
@login_required
@admin_required
def create_invite():
    email = (request.form.get("email") or "").strip().lower()
    role_raw = (request.form.get("role") or UserRole.cashier.value).strip().lower()
    if not email:
        flash("Invite email is required.", "warning")
        return redirect(url_for("settings.access_dashboard"))

    try:
        role = UserRole(role_raw)
    except ValueError:
        role = UserRole.cashier

    now = datetime.utcnow()
    token = secrets.token_urlsafe(24)
    expires_at = now + timedelta(hours=72)

    existing = (
        UserInvite.query.filter(
            UserInvite.email == email,
            UserInvite.status.in_(("pending", "sent")),
        )
        .order_by(UserInvite.created_at.desc())
        .first()
    )

    if existing:
        existing.role = role
        existing.token = token
        existing.expires_at = expires_at
        existing.last_sent_at = now
        existing.status = "sent"
        invite = existing
    else:
        inviter = _current_user()
        invite = UserInvite(
            email=email,
            role=role,
            token=token,
            expires_at=expires_at,
            invited_by_id=inviter.id if inviter else None,
            status="sent",
            last_sent_at=now,
        )
        db.session.add(invite)

    db.session.commit()
    invite_url = url_for("auth.register", token=token, _external=True)
    log_event(
        "user_invite_created",
        resource_type="user_invite",
        resource_id=invite.id,
        after={"email": email, "role": role.value},
    )
    flash(f"Invite ready. Share this link: {invite_url}", "success")
    return redirect(url_for("settings.access_dashboard"))


@settings_bp.route("/access/invite/<int:invite_id>/resend", methods=["POST"])
@login_required
@admin_required
def resend_invite(invite_id: int):
    invite = UserInvite.query.get_or_404(invite_id)
    invite.last_sent_at = datetime.utcnow()
    invite.expires_at = datetime.utcnow() + timedelta(hours=72)
    if not invite.token:
        invite.token = secrets.token_urlsafe(24)
    if invite.status in ("pending", "sent"):
        invite.status = "sent"
    db.session.commit()
    invite_url = url_for("auth.register", token=invite.token, _external=True)
    log_event(
        "user_invite_resent",
        resource_type="user_invite",
        resource_id=invite.id,
        after={"email": invite.email},
    )
    flash(f"Invite refreshed. New link: {invite_url}", "success")
    return redirect(url_for("settings.access_dashboard"))


@settings_bp.route("/access/invite/<int:invite_id>/revoke", methods=["POST"])
@login_required
@admin_required
def revoke_invite(invite_id: int):
    invite = UserInvite.query.get_or_404(invite_id)
    invite.status = "revoked"
    invite.expires_at = datetime.utcnow()
    db.session.commit()
    log_event(
        "user_invite_revoked",
        resource_type="user_invite",
        resource_id=invite.id,
        after={"email": invite.email},
    )
    flash("Invite revoked.", "info")
    return redirect(url_for("settings.access_dashboard"))


@settings_bp.route("/access/users/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def update_role(user_id: int):
    user = User.query.get_or_404(user_id)
    role_raw = (request.form.get("role") or "").strip().lower()
    try:
        role = UserRole(role_raw)
    except ValueError:
        flash("Invalid role selected.", "warning")
        return redirect(url_for("settings.access_dashboard"))

    user.role = role
    db.session.commit()
    log_event(
        "user_role_updated",
        resource_type="user",
        resource_id=user.id,
        after={"role": role.value},
    )
    flash(f"{user.username} is now a {role.value}.", "success")
    return redirect(url_for("settings.access_dashboard"))


@settings_bp.route("/access/sessions/<int:session_id>/revoke", methods=["POST"])
@login_required
@admin_required
def revoke_session(session_id: int):
    record = UserSession.query.get_or_404(session_id)
    if record.revoked_at:
        flash("Session already revoked.", "info")
        return redirect(url_for("settings.access_dashboard"))

    record.revoked_at = datetime.utcnow()
    db.session.commit()
    log_event(
        "session_revoked",
        resource_type="user_session",
        resource_id=record.id,
        after={"user": record.user.username if record.user else None},
    )
    flash("Session revoked.", "success")
    return redirect(url_for("settings.access_dashboard"))


@settings_bp.route("/connect")
@login_required
@admin_required
def connect_hub():
    return render_template("settings/connect.html", **_connect_context())


@settings_bp.route("/connect/qr", methods=["POST"])
@login_required
@admin_required
def connect_qr():
    payment_url = (request.form.get("payment_url") or "").strip()
    review_url = (request.form.get("review_url") or "").strip()

    preview = {
        "payment_url": payment_url,
        "review_url": review_url,
        "payment_qr": qr_to_base64(payment_url) if payment_url else "",
        "review_qr": qr_to_base64(review_url) if review_url else "",
    }
    flash("Preview updated. Download the signage when ready.", "success")
    return render_template("settings/connect.html", **_connect_context(preview))


@settings_bp.route("/connect/webhooks", methods=["POST"])
@login_required
@admin_required
def create_webhook():
    provider = (request.form.get("provider") or "").strip().lower()
    event_name = (request.form.get("event") or "").strip().lower()
    target_url = (request.form.get("target_url") or "").strip() or None
    secret = (request.form.get("secret") or "").strip()

    retry_window_raw = request.form.get("retry_window") or ""
    try:
        retry_window = max(5, min(int(retry_window_raw or 15), 120))
    except ValueError:
        retry_window = 15

    if not provider or not event_name:
        flash("Provider and event are required.", "warning")
        return redirect(url_for("settings.connect_hub"))

    secret = secret or secrets.token_urlsafe(18)
    webhook = ApiWebhook.query.filter_by(provider=provider, event=event_name).first()
    if webhook:
        webhook.target_url = target_url
        webhook.secret = secret
        webhook.retry_window = retry_window
        webhook.status = "active"
    else:
        webhook = ApiWebhook(
            provider=provider,
            event=event_name,
            target_url=target_url,
            secret=secret,
            retry_window=retry_window,
            status="active",
        )
        db.session.add(webhook)
    db.session.commit()
    log_event(
        "webhook_configured",
        resource_type="api_webhook",
        resource_id=webhook.id,
        after={"provider": provider, "event": event_name},
    )
    flash(f"Webhook saved. Secret: {secret}", "success")
    return redirect(url_for("settings.connect_hub"))


@settings_bp.route("/connect/webhooks/<int:webhook_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_webhook(webhook_id: int):
    webhook = ApiWebhook.query.get_or_404(webhook_id)
    webhook.status = "inactive" if webhook.status == "active" else "active"
    db.session.commit()
    log_event(
        "webhook_toggled",
        resource_type="api_webhook",
        resource_id=webhook.id,
        after={"status": webhook.status},
    )
    flash(f"Webhook marked as {webhook.status}.", "success")
    return redirect(url_for("settings.connect_hub"))


@settings_bp.route("/connect/webhooks/<int:webhook_id>/rotate", methods=["POST"])
@login_required
@admin_required
def rotate_webhook_secret(webhook_id: int):
    webhook = ApiWebhook.query.get_or_404(webhook_id)
    webhook.secret = secrets.token_urlsafe(18)
    db.session.commit()
    log_event(
        "webhook_secret_rotated",
        resource_type="api_webhook",
        resource_id=webhook.id,
    )
    flash(f"Secret rotated. New secret: {webhook.secret}", "success")
    return redirect(url_for("settings.connect_hub"))


@settings_bp.route("/connect/events/<int:event_id>/retry", methods=["POST"])
@login_required
@admin_required
def retry_webhook_event(event_id: int):
    event = WebhookEvent.query.get_or_404(event_id)
    event.status = "pending"
    event.next_retry_at = datetime.utcnow()
    event.last_error = None
    event.processed_at = None
    db.session.commit()
    log_event(
        "webhook_event_retry",
        resource_type="webhook_event",
        resource_id=event.id,
    )
    flash("Event queued for retry.", "success")
    return redirect(url_for("settings.connect_hub"))


@settings_bp.route("/connect/events/<int:event_id>/match", methods=["POST"])
@login_required
@admin_required
def match_webhook_event(event_id: int):
    event = WebhookEvent.query.get_or_404(event_id)
    reference = (request.form.get("match_reference") or "").strip()
    if not reference:
        flash("Provide an invoice number or sale ID to match.", "warning")
        return redirect(url_for("settings.connect_hub"))

    sale: Sale | None = None
    if reference.isdigit():
        sale = Sale.query.get(int(reference))
    if not sale:
        sale = Sale.query.filter_by(invoice_number=reference).first()
    if not sale:
        flash("Could not locate a sale with that reference.", "warning")
        return redirect(url_for("settings.connect_hub"))

    event.matched_sale_id = sale.id
    event.status = "matched"
    event.processed_at = datetime.utcnow()
    event.last_error = None
    db.session.commit()
    log_event(
        "webhook_event_matched",
        resource_type="webhook_event",
        resource_id=event.id,
        after={"sale_id": sale.id},
    )
    flash(f"Event linked to sale #{sale.id}.", "success")
    return redirect(url_for("settings.connect_hub"))


@settings_bp.route("/plan/start-trial", methods=["POST"])
@login_required
@admin_required
def start_plan_trial():
    profile = ShopProfile.query.get(1)
    if not profile:
        flash("Shop profile not initialised yet.", "warning")
        return redirect(url_for("settings.branding"))

    _ensure_base_plan(profile)

    requested_slug = (request.form.get("plan") or "pro").strip().lower()
    plan = (
        Plan.query.filter(Plan.slug == requested_slug, Plan.is_active.is_(True)).first()
    )
    if not plan:
        flash("Selected plan is not available right now.", "warning")
        return redirect(request.referrer or url_for("settings.branding"))

    if not plan.trial_days:
        flash(f"{plan.name} does not offer a trial.", "info")
        return redirect(request.referrer or url_for("settings.branding"))

    now = datetime.utcnow()
    active_trial_same_plan = profile.trial_active and profile.trial_plan_slug == plan.slug
    if active_trial_same_plan:
        flash(f"You are already on a {plan.name} trial.", "info")
        return redirect(request.referrer or url_for("settings.branding"))

    profile.trial_plan_slug = plan.slug
    profile.trial_started_at = now
    profile.trial_ends_at = now + timedelta(days=int(plan.trial_days))
    profile.trial_cancelled_at = None
    log_event(
        "subscription_trial_start",
        resource_type="plan",
        resource_id=plan.id,
        before={"base_plan": profile.plan_slug},
        after={
            "trial_plan": plan.slug,
            "trial_ends_at": profile.trial_ends_at.isoformat() if profile.trial_ends_at else None,
        },
    )
    db.session.commit()

    session["plan"] = profile.active_plan_slug()
    flash(f"{plan.name} trial activated for {plan.trial_days} days.", "success")
    return redirect(request.referrer or url_for("settings.branding"))


@settings_bp.route("/plan/cancel-trial", methods=["POST"])
@login_required
@admin_required
def cancel_plan_trial():
    profile = ShopProfile.query.get(1)
    if not profile or not profile.trial_active:
        flash("There is no active trial to cancel.", "info")
        return redirect(request.referrer or url_for("settings.branding"))

    ended_at = datetime.utcnow()
    log_event(
        "subscription_trial_cancel",
        resource_type="plan",
        resource_id=None,
        before={
            "trial_plan": profile.trial_plan_slug,
            "trial_ends_at": profile.trial_ends_at.isoformat() if profile.trial_ends_at else None,
        },
        after={"ended_at": ended_at.isoformat()},
    )
    profile.trial_plan_slug = None
    profile.trial_cancelled_at = ended_at
    db.session.commit()

    session["plan"] = profile.active_plan_slug()
    flash("Trial ended. You are back on your base plan.", "info")
    return redirect(request.referrer or url_for("settings.branding"))


@settings_bp.route("/profile/download-data")
@login_required
def download_profile_data():
    username = session.get("user")
    if not username:
        flash("Please login again to download your data.", "warning")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(username=username).first()
    if not user:
        flash("Account not found.", "warning")
        return redirect(url_for("auth.login"))

    completions = [
        {
            "code": completion.quest.code if completion.quest else None,
            "title": completion.quest.title if completion.quest else None,
            "completed_at": completion.completed_at.isoformat() if completion.completed_at else None,
        }
        for completion in UserQuest.query.filter_by(user_id=user.id)
        .order_by(UserQuest.completed_at.desc())
        .all()
    ]

    referrals = [
        {
            "code": referral.code,
            "status": referral.status,
            "invitee_id": referral.invitee_id,
            "created_at": referral.created_at.isoformat() if referral.created_at else None,
        }
        for referral in Referral.query.filter_by(inviter_id=user.id).all()
    ]

    events = [
        {
            "name": event.name,
            "props": event.props,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }
        for event in Event.query.filter_by(user_id=user.id)
        .order_by(Event.created_at.desc())
        .limit(200)
        .all()
    ]

    payload = {
        "user": {
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "streak_count": user.streak_count,
            "xp": user.xp,
            "last_active_at": user.last_active_at.isoformat() if user.last_active_at else None,
            "engagement_opt_out": user.engagement_opt_out,
        },
        "quests_completed": completions,
        "referrals": referrals,
        "events": events,
    }

    response = current_app.response_class(
        json.dumps(payload, default=str, indent=2),
        mimetype="application/json",
    )
    response.headers["Content-Disposition"] = f"attachment; filename=shopapp-data-{username}.json"
    return response
