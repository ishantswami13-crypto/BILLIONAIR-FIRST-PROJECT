from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ...extensions import db
from ...models.catalog import Product

bp = Blueprint("inventory", __name__)


@bp.post("/products")
@jwt_required()
def create_product():
    ident = get_jwt_identity() or {}
    org_id = ident.get("org_id")
    data = request.get_json() or {}
    p = Product(
        org_id=org_id,
        sku=data.get("sku"),
        name=data.get("name"),
        unit=data.get("unit", "pcs"),
        price=data.get("price", 0),
        tax_rate=data.get("tax_rate", 0),
        opening_stock=data.get("opening_stock", 0),
    )
    db.session.add(p)
    db.session.commit()
    return {"id": p.id, "name": p.name}, 201


@bp.get("/products")
@jwt_required()
def list_products():
    ident = get_jwt_identity() or {}
    org_id = ident.get("org_id")
    rows = db.session.scalars(db.select(Product).filter_by(org_id=org_id)).all()
    return {
        "products": [
            {
                "id": r.id,
                "sku": r.sku,
                "name": r.name,
                "unit": r.unit,
                "price": float(r.price or 0),
                "tax_rate": float(r.tax_rate or 0),
                "opening_stock": float(r.opening_stock or 0),
            }
            for r in rows
        ]
    }
