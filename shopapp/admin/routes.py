from flask import Blueprint, render_template, request
from sqlalchemy import or_

from ..models import User
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
