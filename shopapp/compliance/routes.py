from __future__ import annotations

from flask import Blueprint, abort, jsonify

from ..extensions import db
from ..models import EInvoiceSubmission, Sale
from .services import get_gst_service

compliance_bp = Blueprint("compliance", __name__, url_prefix="/compliance")


@compliance_bp.get("/gst/status/<int:sale_id>")
def gst_status(sale_id: int):
    sale = Sale.query.get(sale_id)
    if not sale:
        abort(404, description="Sale not found.")

    if not sale.irn:
        return jsonify({"sale_id": sale_id, "status": sale.gst_status})

    service = get_gst_service()
    if not service.is_configured():
        return jsonify({"sale_id": sale_id, "status": sale.gst_status, "detail": "GST provider not configured."})

    response = service.fetch_status(sale.irn)
    return jsonify(response)


@compliance_bp.get("/gst/submissions/<int:sale_id>")
def gst_submissions(sale_id: int):
    submissions = (
        EInvoiceSubmission.query.filter_by(sale_id=sale_id)
        .order_by(EInvoiceSubmission.created_at.desc())
        .all()
    )
    return jsonify([
        {
            "id": submission.id,
            "status": submission.status,
            "created_at": submission.created_at.isoformat() if submission.created_at else None,
            "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
            "acknowledged_at": submission.acknowledged_at.isoformat() if submission.acknowledged_at else None,
            "error": submission.error_message,
        }
        for submission in submissions
    ])


@compliance_bp.post("/gst/submissions/<int:sale_id>/retry")
def retry_submission(sale_id: int):
    sale = Sale.query.get(sale_id)
    if not sale:
        abort(404, description="Sale not found.")

    service = get_gst_service()
    payload = {"stub": True, "sale_id": sale_id}
    response = service.submit_einvoice(sale_id, payload)

    record = EInvoiceSubmission(
        sale_id=sale_id,
        status=response.get("status", "queued"),
        payload=str(payload),
        response=str(response),
    )
    db.session.add(record)
    db.session.commit()

    return jsonify({"message": "Retry queued", "submission_id": record.id}), 202
