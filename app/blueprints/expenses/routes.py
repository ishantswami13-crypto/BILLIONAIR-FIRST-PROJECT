from flask import Blueprint

bp = Blueprint("expenses", __name__)


@bp.get("/")
def expenses_ping():
    return {"ready": True}
