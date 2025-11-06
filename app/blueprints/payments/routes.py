from flask import Blueprint, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from decimal import Decimal
from ...extensions import db
from ...models.sales import Invoice, Payment
from ...services.upi import get_upi_provider
from ...utils.feature_flags import is_enabled

bp = Blueprint("payments", __name__)


@bp.post("/collect")
@jwt_required()
def create_collect():
    if not is_enabled("UPI"):
        return {"error": "UPI disabled"}, 400
    ident = get_jwt_identity() or {}
    org_id = ident.get("org_id")
    data = request.get_json() or {}
    invoice_id = data.get("invoice_id")
    payee_vpa = data.get("payee_vpa", "merchant@upi")
    inv = db.session.get(Invoice, invoice_id)
    if not inv or inv.org_id != org_id:
        return {"error": "invoice not found"}, 404
    provider = get_upi_provider(current_app.config.get("PSP_PROVIDER"))
    payload = provider.create_collect_request(
        payee_vpa=payee_vpa,
        amount=float(inv.total or Decimal(0)),
        txn_note=f"Invoice {inv.number}",
        invoice_number=inv.number or str(inv.id),
    )
    return {"invoice_id": inv.id, **payload}


@bp.post("/webhook/mock-paid")
def webhook_mock_paid():
    data = request.get_json() or {}
    invoice_id = data.get("invoice_id")
    ref = data.get("ref", "MOCKREF")
    amount = Decimal(str(data.get("amount", 0)))
    inv = db.session.get(Invoice, invoice_id)
    if not inv:
        return {"error": "invoice not found"}, 404
    inv.status = "paid"
    pay = Payment(invoice_id=inv.id, org_id=inv.org_id, amount=amount, ref=ref, method="UPI")
    db.session.add(pay)
    db.session.commit()
    return {"ok": True}
