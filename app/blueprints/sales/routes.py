from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from decimal import Decimal
from ...extensions import db
from ...models.sales import Invoice, InvoiceItem, Customer, Payment

bp = Blueprint("sales", __name__)


def _d(v):
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal(0)


@bp.post("/customers")
@jwt_required()
def create_customer():
    ident = get_jwt_identity() or {}
    org_id = ident.get("org_id")
    data = request.get_json() or {}
    c = Customer(org_id=org_id, name=data.get("name"), phone=data.get("phone"), gstin=data.get("gstin"))
    db.session.add(c)
    db.session.commit()
    return {"id": c.id, "name": c.name}, 201


@bp.post("/invoice")
@jwt_required()
def create_invoice():
    ident = get_jwt_identity() or {}
    org_id = ident.get("org_id")
    data = request.get_json() or {}

    items = data.get("items", [])
    subtotal = Decimal(0)
    taxtotal = Decimal(0)
    for it in items:
        qty = _d(it.get("qty", 1))
        rate = _d(it.get("rate", 0))
        tax_rate = _d(it.get("tax_rate", 0))
        line_no_tax = qty * rate
        tax_val = (line_no_tax * tax_rate) / Decimal(100)
        subtotal += line_no_tax
        taxtotal += tax_val

    inv = Invoice(
        org_id=org_id,
        store_id=data.get("store_id"),
        customer_id=data.get("customer_id"),
        number=data.get("number"),
        subtotal=subtotal,
        tax_total=taxtotal,
        total=subtotal + taxtotal,
        status="due",
    )
    db.session.add(inv)
    db.session.flush()

    for it in items:
        qty = _d(it.get("qty", 1))
        rate = _d(it.get("rate", 0))
        tax_rate = _d(it.get("tax_rate", 0))
        line_total = (qty * rate) * (Decimal(1) + tax_rate / Decimal(100))
        db.session.add(
            InvoiceItem(
                invoice_id=inv.id,
                product_id=it.get("product_id"),
                description=it.get("description"),
                qty=qty,
                rate=rate,
                tax_rate=tax_rate,
                line_total=line_total,
            )
        )

    db.session.commit()
    return {"id": inv.id, "number": inv.number, "total": float(inv.total)}, 201


@bp.get("/invoices")
@jwt_required()
def list_invoices():
    ident = get_jwt_identity() or {}
    org_id = ident.get("org_id")
    rows = db.session.scalars(db.select(Invoice).filter_by(org_id=org_id)).all()
    return {
        "invoices": [
            {"id": r.id, "number": r.number, "total": float(r.total or 0), "status": r.status} for r in rows
        ]
    }


@bp.post("/invoices/mark-paid")
@jwt_required()
def mark_paid():
    inv_id = int((request.args.get("id") or request.get_json().get("id") or 0))
    inv = db.session.get(Invoice, inv_id)
    if not inv:
        return {"error": "invoice not found"}, 404
    inv.status = "paid"
    db.session.commit()
    return {"ok": True}


@bp.post("/payment-record")
@jwt_required()
def record_payment():
    ident = get_jwt_identity() or {}
    org_id = ident.get("org_id")
    data = request.get_json() or {}
    pay = Payment(
        invoice_id=data.get("invoice_id"),
        org_id=org_id,
        method=data.get("method", "UPI"),
        amount=_d(data.get("amount", 0)),
        ref=data.get("ref"),
    )
    db.session.add(pay)
    inv = db.session.get(Invoice, data.get("invoice_id"))
    if inv:
        inv.status = "paid"
    db.session.commit()
    return {"id": pay.id}
