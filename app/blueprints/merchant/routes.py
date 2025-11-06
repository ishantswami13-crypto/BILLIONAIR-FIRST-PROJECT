from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ...extensions import db
from ...models.core import Store

bp = Blueprint("merchant", __name__)


@bp.post("/stores")
@jwt_required()
def create_store():
    ident = get_jwt_identity() or {}
    org_id = ident.get("org_id")
    data = request.get_json() or {}
    store = Store(org_id=org_id, name=data.get("name", "Main Store"), address=data.get("address"))
    db.session.add(store)
    db.session.commit()
    return {"id": store.id, "name": store.name}, 201


@bp.get("/stores")
@jwt_required()
def list_stores():
    ident = get_jwt_identity() or {}
    org_id = ident.get("org_id")
    rows = db.session.scalars(db.select(Store).filter_by(org_id=org_id)).all()
    return {"stores": [{"id": s.id, "name": s.name} for s in rows]}
