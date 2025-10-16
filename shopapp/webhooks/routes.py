from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import ApiWebhook, Sale, WebhookEvent
from ..utils.audit import log_event

webhooks_bp = Blueprint("webhooks", __name__, url_prefix="/api/webhooks")


def _extract_external_id(payload: dict[str, Any], headers) -> str | None:
    keys = (
        "event_id",
        "id",
        "transaction_id",
        "payment_id",
        "reference",
        "order_id",
        "invoice_number",
    )
    for key in keys:
        value = payload.get(key)
        if value:
            return str(value)
    return headers.get("X-Request-Id") or headers.get("X-Webhook-Id")


def _match_sale(payload: dict[str, Any]) -> Sale | None:
    sale = None
    candidates = [
        payload.get("sale_id"),
        payload.get("saleId"),
        payload.get("transaction_sale_id"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            sale = Sale.query.get(int(candidate))
        except (TypeError, ValueError):
            continue
        if sale:
            return sale

    invoice = payload.get("invoice_number") or payload.get("invoice") or payload.get("order_id")
    if invoice:
        sale = Sale.query.filter_by(invoice_number=str(invoice)).first()
        if sale:
            return sale

    reference = payload.get("reference") or payload.get("txn_reference")
    if reference:
        sale = Sale.query.filter_by(invoice_number=str(reference)).first()
    return sale


@webhooks_bp.route("/<provider>/<event>", methods=["POST"])
def ingest_webhook(provider: str, event: str):
    provider = provider.lower()
    event = event.lower()
    config = ApiWebhook.query.filter_by(provider=provider, event=event).first()
    if not config or config.status != "active":
        log_event(
            "webhook_ignored",
            resource_type="api_webhook",
            resource_id=config.id if config else None,
            after={"provider": provider, "event": event},
        )
        return jsonify({"status": "ignored"}), 404

    secret_header = request.headers.get("X-Shopapp-Secret") or request.headers.get("X-Webhook-Secret")
    raw_payload = request.get_json(silent=True)
    if raw_payload is None:
        raw_payload = request.form.to_dict(flat=True) or {}

    serialized_payload = json.dumps(raw_payload, default=str)
    external_id = _extract_external_id(raw_payload, request.headers)
    now = datetime.utcnow()

    if config.secret and config.secret != secret_header:
        event_record = WebhookEvent(
            webhook_id=config.id,
            external_id=external_id,
            status="rejected",
            attempts=1,
            payload=serialized_payload,
            last_error="Secret mismatch",
            created_at=now,
        )
        db.session.add(event_record)
        db.session.commit()
        log_event(
            "webhook_rejected",
            resource_type="webhook_event",
            resource_id=event_record.id,
            after={"reason": "secret_mismatch", "provider": provider, "event": event},
        )
        return jsonify({"status": "rejected"}), 403

    sale = _match_sale(raw_payload)
    status = "matched" if sale else "pending"

    event_record = WebhookEvent(
        webhook_id=config.id,
        external_id=external_id,
        status=status,
        attempts=1,
        payload=serialized_payload,
        matched_sale_id=sale.id if sale else None,
        created_at=now,
        processed_at=now if sale else None,
        next_retry_at=(now + timedelta(minutes=config.retry_window or 15)) if not sale else None,
    )
    db.session.add(event_record)

    if sale:
        config.last_success_at = now

    db.session.commit()

    log_event(
        "webhook_ingested",
        resource_type="webhook_event",
        resource_id=event_record.id,
        after={
            "provider": provider,
            "event": event,
            "status": status,
            "external_id": external_id,
            "sale_id": sale.id if sale else None,
        },
    )

    return jsonify({"status": status, "matched_sale_id": sale.id if sale else None}), 202
