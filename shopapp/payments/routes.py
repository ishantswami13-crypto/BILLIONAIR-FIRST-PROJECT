from __future__ import annotations

import json
from datetime import datetime

from flask import Blueprint, abort, current_app, jsonify, render_template, request

from ..extensions import db
from ..models import PaymentIntent, PaymentTransaction
from ..utils.decorators import login_required
from .service import get_payments_service

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")


def _provider_secret(provider: str) -> str | None:
    cfg = current_app.config
    if provider == "razorpay":
        return cfg.get("RAZORPAY_WEBHOOK_SECRET")
    if provider == "stripe":
        return cfg.get("STRIPE_WEBHOOK_SECRET")
    return None


def _signature_header(provider: str) -> str:
    if provider == "razorpay":
        return "X-Razorpay-Signature"
    if provider == "stripe":
        return "Stripe-Signature"
    return "X-Signature"


def _verify_signature(provider: str) -> bool:
    secret = _provider_secret(provider)
    if not secret:
        # No secret configured, accept payload for sandbox purposes.
        return True
    signature = request.headers.get(_signature_header(provider))
    return bool(signature and signature.strip() == secret.strip())


def _normalize_status(provider: str, payload: dict) -> str:
    status = payload.get("status") or payload.get("event") or "received"
    status = str(status).lower()
    if "." in status:
        status = status.split(".", 1)[-1]
    return status


def _extract_amount(payload: dict) -> float:
    amount = payload.get("amount") or payload.get("amount_paid") or payload.get("amount_received")
    try:
        return float(amount or 0)
    except (TypeError, ValueError):
        return 0.0


@payments_bp.post("/webhook/<provider>")
def webhook(provider: str):
    provider = provider.lower()
    if provider not in {"razorpay", "stripe"}:
        abort(404)
    if not _verify_signature(provider):
        abort(400, description="Invalid webhook signature.")

    payload = request.get_json(silent=True)
    if payload is None:
        abort(400, description="Invalid JSON payload.")

    intent_id = payload.get("intent_id") or payload.get("metadata", {}).get("intent_id")
    transaction_id = payload.get("transaction_id")
    reference = payload.get("reference") or payload.get("id")
    status = _normalize_status(provider, payload)
    amount = _extract_amount(payload)

    txn = None
    if transaction_id:
        txn = PaymentTransaction.query.filter_by(id=transaction_id).first()
    intent_lookup_id = None
    if intent_id is not None:
        try:
            intent_lookup_id = int(intent_id)
        except (TypeError, ValueError):
            abort(400, description="Invalid intent reference.")

    if not txn and intent_lookup_id is not None:
        txn = (
            PaymentTransaction.query.filter_by(intent_id=intent_lookup_id)
            .order_by(PaymentTransaction.created_at.desc())
            .first()
        )

    if txn:
        txn.status = status or txn.status
        txn.reference = reference or txn.reference
        if amount:
            txn.amount = amount
        txn.raw_response = json.dumps(payload)
        txn.error = payload.get("error_reason") or payload.get("error") or ""
        txn.processed_at = datetime.utcnow()
        intent = txn.intent
    else:
        if intent_lookup_id is None:
            abort(400, description="Intent reference missing.")
        intent = PaymentIntent.query.get(intent_lookup_id)
        if not intent:
            abort(404, description="Payment intent not found.")
        txn = PaymentTransaction(
            intent=intent,
            provider=provider,
            status=status or "received",
            amount=amount or intent.amount,
            reference=reference,
            raw_response=json.dumps(payload),
            processed_at=datetime.utcnow(),
        )
        db.session.add(txn)

    if intent:
        if status in {"captured", "paid", "succeeded", "success"}:
            intent.status = "captured"
        elif status in {"failed", "cancelled", "refunded"}:
            intent.status = status
        else:
            intent.status = status or intent.status
        intent.updated_at = datetime.utcnow()
        db.session.add(intent)

    db.session.add(txn)
    db.session.commit()
    return jsonify({"status": "ok"}), 202


@payments_bp.get("/intents")
@login_required
def list_intents():
    try:
        limit = min(max(int(request.args.get("limit", 50)), 1), 200)
    except (TypeError, ValueError):
        limit = 50
    try:
        offset = max(int(request.args.get("offset", 0)), 0)
    except (TypeError, ValueError):
        offset = 0

    rows = (
        PaymentIntent.query.order_by(PaymentIntent.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return jsonify(
        [
            {
                "id": intent.id,
                "sale_id": intent.sale_id,
                "amount": intent.amount,
                "currency": intent.currency,
                "provider": intent.provider,
                "status": intent.status,
                "updated_at": intent.updated_at.isoformat() if intent.updated_at else None,
            }
            for intent in rows
        ]
    )


@payments_bp.get("/intents/dashboard")
@login_required
def intents_dashboard():
    query = PaymentIntent.query.order_by(PaymentIntent.created_at.desc())
    intents = query.limit(100).all()
    total_amount = sum(intent.amount for intent in intents)
    captured_amount = sum(intent.amount for intent in intents if intent.status == "captured")
    captured_count = sum(1 for intent in intents if intent.status == "captured")
    providers = get_payments_service().list_providers()
    return render_template(
        "payments/intents.html",
        intents=intents,
        total_amount=total_amount,
        captured_amount=captured_amount,
        captured_count=captured_count,
        providers=providers,
    )
