from __future__ import annotations

import os
from dataclasses import dataclass

from flask import Blueprint, abort, current_app, jsonify, request
import razorpay

bp = Blueprint("payments_api", __name__, url_prefix="/api/payments")


@dataclass(frozen=True)
class RazorpayCredentials:
    key_id: str
    key_secret: str
    webhook_secret: str | None = None


def _load_credentials() -> RazorpayCredentials:
    key_id = (
        os.environ.get("RAZORPAY_KEY_ID")
        or current_app.config.get("RAZORPAY_KEY_ID")
    )
    key_secret = (
        os.environ.get("RAZORPAY_KEY_SECRET")
        or current_app.config.get("RAZORPAY_KEY_SECRET")
    )
    webhook_secret = (
        os.environ.get("RAZORPAY_WEBHOOK_SECRET")
        or current_app.config.get("RAZORPAY_WEBHOOK_SECRET")
    )
    if not key_id or not key_secret:
        current_app.logger.error("Razorpay credentials missing. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.")
        abort(500, description="Payment processor unavailable.")
    return RazorpayCredentials(key_id=key_id, key_secret=key_secret, webhook_secret=webhook_secret)


def _get_client(creds: RazorpayCredentials) -> razorpay.Client:
    return razorpay.Client(auth=(creds.key_id, creds.key_secret))


PLAN_AMT = {
    "pro": 19900,    # INR 199.00
    "elite": 49900,  # INR 499.00
}


@bp.post("/create-order")
def create_order():
    creds = _load_credentials()
    client = _get_client(creds)

    plan = request.args.get("plan", "pro").lower()
    amount = PLAN_AMT.get(plan)
    if not amount:
        return jsonify({"error": "invalid plan"}), 400

    try:
        order = client.order.create(
            {
                "amount": amount,
                "currency": "INR",
                "payment_capture": 1,
                "notes": {"plan": plan},
            }
        )
    except razorpay.errors.BadRequestError as exc:
        current_app.logger.exception("Failed to create Razorpay order: %s", exc)
        return jsonify({"error": "order_creation_failed"}), 502

    # Request objects in this codebase sometimes set request.user
    user = getattr(request, "user", None)
    customer = {
        "name": getattr(user, "name", "") or "Evara User",
        "email": getattr(user, "email", "") or "",
        "contact": getattr(user, "phone", "") or "",
    }

    return jsonify({"key": creds.key_id, "order": order, "customer": customer})


@bp.post("/verify")
def verify_payment():
    creds = _load_credentials()
    client = _get_client(creds)

    payload = request.get_json(force=True, silent=True)
    required_fields = {"razorpay_order_id", "razorpay_payment_id", "razorpay_signature"}
    if not payload or not required_fields.issubset(payload):
        return jsonify({"status": "invalid_payload"}), 400

    try:
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": payload["razorpay_order_id"],
                "razorpay_payment_id": payload["razorpay_payment_id"],
                "razorpay_signature": payload["razorpay_signature"],
            }
        )
    except razorpay.errors.SignatureVerificationError:
        return jsonify({"status": "invalid_signature"}), 400

    # TODO: Persist successful payment to subscription table.
    return jsonify({"status": "ok"})


@bp.post("/webhook")
def webhook():
    creds = _load_credentials()
    if not creds.webhook_secret:
        abort(400, description="Webhook secret not configured.")

    signature = request.headers.get("X-Razorpay-Signature")
    if not signature:
        abort(400, description="Signature header missing.")
    body = request.data.decode("utf-8")

    try:
        razorpay.utility.verify_webhook_signature(body, signature, creds.webhook_secret)
    except razorpay.errors.SignatureVerificationError:
        abort(400, description="Invalid webhook signature.")

    payload = request.get_json(force=True, silent=True)
    event = payload.get("event")
    current_app.logger.info("Razorpay webhook received: %s", event)

    # TODO: Handle payment.captured and payment.failed events.

    return ("", 204)
