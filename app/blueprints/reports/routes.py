from flask import Blueprint

bp = Blueprint("reports", __name__)


@bp.get("/ping")
def ping():
    return {"ok": True}
