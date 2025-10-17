import json
from datetime import datetime

from flask import Blueprint, make_response, render_template, request
from sqlalchemy import or_

from ..models import AuditLog, User
from ..utils.exports import build_audit_log_csv, generate_ca_bundle
from ..utils.decorators import admin_required, login_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/users")
@login_required
@admin_required
def users_admin():
    page = max(int(request.args.get("page", 1) or 1), 1)
    per_page = 25
    query_text = (request.args.get("q") or "").strip()

    query = User.query
    if query_text:
        like = f"%{query_text}%"
        filters = [
            User.username.ilike(like),
            User.email.ilike(like),
            User.phone.ilike(like),
        ]
        query = query.filter(or_(*filters))

    rows = (
        query.order_by(User.id.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return render_template(
        "admin/users.html",
        users=rows.items,
        p=rows,
        q=query_text,
    )


@admin_bp.route("/audit-log")
@login_required
@admin_required
def audit_log():
    page = max(int(request.args.get("page", 1) or 1), 1)
    per_page = 25
    search = (request.args.get("q") or "").strip()

    query = AuditLog.query.order_by(AuditLog.ts.desc())
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                AuditLog.user.ilike(like),
                AuditLog.action.ilike(like),
                AuditLog.details.ilike(like),
            )
        )

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    entries = []
    for row in pagination.items:
        def _as_dict(raw: str | None) -> dict[str, object]:
            if not raw:
                return {}
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    return data
            except (ValueError, TypeError):
                return {}
            return {}

        before = _as_dict(row.before_state)
        after = _as_dict(row.after_state)
        diff = {}
        for key in sorted(set(before.keys()) | set(after.keys())):
            if before.get(key) != after.get(key):
                diff[key] = {
                    "before": before.get(key),
                    "after": after.get(key),
                }

        entries.append(
            {
                "row": row,
                "before": before,
                "after": after,
                "diff": diff,
            }
        )

    return render_template(
        "admin/audit_log.html",
        entries=entries,
        page=pagination,
        q=search,
    )


@admin_bp.route("/audit-log/export.csv")
@login_required
@admin_required
def audit_log_export():
    entries = AuditLog.query.order_by(AuditLog.ts.asc()).all()
    csv_data = build_audit_log_csv(entries)
    response = make_response(csv_data)
    response.headers["Content-Type"] = "text/csv"
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    response.headers["Content-Disposition"] = f"attachment; filename=audit_log_{stamp}.csv"
    return response


@admin_bp.route("/exports/ca-bundle")
@login_required
@admin_required
def export_ca_bundle():
    try:
        days = int(request.args.get("days", 30))
    except (TypeError, ValueError):
        days = 30

    bundle_bytes, filename = generate_ca_bundle(days=days)
    response = make_response(bundle_bytes)
    response.headers["Content-Type"] = "application/zip"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response
