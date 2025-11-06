from flask import Blueprint, request
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from ...extensions import db
from ...models.core import Org, User
from ...utils.security import hash_password, verify_password

bp = Blueprint("auth", __name__)


@bp.post("/register")
def register():
    data = request.get_json() or {}
    org_name = data.get("org_name") or "My Org"
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return {"error": "email and password required"}, 400
    if db.session.scalar(db.select(User).filter_by(email=email)):
        return {"error": "email already exists"}, 400

    org = Org(name=org_name)
    db.session.add(org)
    db.session.flush()

    user = User(org_id=org.id, email=email, password_hash=hash_password(password), role="owner")
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity={"user_id": user.id, "org_id": org.id})
    return {"access_token": token, "org_id": org.id, "user_id": user.id}, 201


@bp.post("/login")
def login():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")
    user = db.session.scalar(db.select(User).filter_by(email=email))
    if not user or not verify_password(password, user.password_hash):
        return {"error": "invalid credentials"}, 401
    token = create_access_token(identity={"user_id": user.id, "org_id": user.org_id})
    return {"access_token": token}


@bp.get("/me")
@jwt_required()
def me():
    ident = get_jwt_identity() or {}
    return {"identity": ident}
