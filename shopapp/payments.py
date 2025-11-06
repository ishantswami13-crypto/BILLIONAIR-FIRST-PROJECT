"""
Lightweight Razorpay integration for subscription checkout.

Exposes a JSON API to create orders that the frontend Razorpay Checkout
widget can consume, plus a webhook endpoint to verify payment events.
"""

from __future__ import annotations

import os
import time
from typing import Any

import razorpay
from flask import Blueprint, abort, current_app, jsonify, render_template_string, request

payments_api_bp = Blueprint("payments_api", __name__)
payments_bp = Blueprint("payments", __name__)

KEY_ID = os.environ.get("RAZORPAY_KEY_ID") or ""
KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET") or ""
WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET") or ""

PLAN_AMOUNTS: dict[str, int] = {
    "pro": 19900,   # ₹199.00
    "elite": 49900  # ₹499.00
}

_client: razorpay.Client | None = None


def _get_client() -> razorpay.Client | None:
    global _client
    if not KEY_ID or not KEY_SECRET:
        return None
    if _client is None:
        _client = razorpay.Client(auth=(KEY_ID, KEY_SECRET))
    return _client


@payments_api_bp.route("/api/subscribe", methods=["POST"])
def create_order() -> tuple[Any, int] | Any:
    client = _get_client()
    if client is None:
        current_app.logger.warning("Razorpay client misconfigured; missing key id/secret")
        return jsonify({"error": "payments_unavailable"}), 503

    payload = request.get_json(silent=True) or {}
    plan = str(payload.get("plan") or "pro").lower().strip()
    amount = PLAN_AMOUNTS.get(plan)
    if amount is None:
        return jsonify({"error": "unknown_plan"}), 400

    receipt = f"evara_{plan}_{int(time.time())}"

    try:
        order = client.order.create(
            {
                "amount": amount,
                "currency": "INR",
                "receipt": receipt,
                "payment_capture": 1,
            }
        )
    except razorpay.errors.BadRequestError as exc:
        current_app.logger.exception("Unable to create Razorpay order: %s", exc)
        return jsonify({"error": "order_failed"}), 502

    prefill = {}
    try:
        user = getattr(request, "user", None)
        if user:
            prefill = {
                "name": getattr(user, "name", "") or "",
                "email": getattr(user, "email", "") or "",
                "contact": getattr(user, "phone", "") or "",
            }
    except Exception:  # pragma: no cover - best effort only
        prefill = {}

    return jsonify(
        {
            "order_id": order.get("id"),
            "amount": order.get("amount"),
            "currency": order.get("currency"),
            "key_id": KEY_ID,
            "prefill": prefill,
        }
    )


@payments_api_bp.route("/webhooks/razorpay", methods=["POST"])
def webhook() -> tuple[str, int]:
    if not WEBHOOK_SECRET:
        abort(503)

    signature = request.headers.get("X-Razorpay-Signature") or ""
    body = request.get_data(as_text=True)

    try:
        razorpay.Utility.verify_webhook_signature(body, signature, WEBHOOK_SECRET)
    except razorpay.errors.SignatureVerificationError:
        current_app.logger.warning("Razorpay signature verification failed")
        abort(400)

    event = request.json or {}
    event_type = event.get("event")

    if event_type == "payment.captured":
        payment = (event.get("payload") or {}).get("payment", {}).get("entity", {})
        order_id = payment.get("order_id")
        amount = payment.get("amount")
        current_app.logger.info("[Razorpay] payment captured order=%s amount=%s", order_id, amount)
        # TODO: persist subscription state for the account tied to this order/plan.

    return "", 200


@payments_bp.route("/subscribe/success")
def subscribe_success() -> str:
    order_id = request.args.get("order_id", "")
    return render_template_string(
        """
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>Subscription active</title>
          <meta name="theme-color" content="#0D0D0F">
          <link rel="icon" type="image/svg+xml" href="/assets/evara-icon.svg">
          <style>
            body{background:#0D0D0F;color:#F5F7FA;font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,"Helvetica Neue",Arial,sans-serif;margin:0;display:grid;place-items:center;min-height:100vh;padding:24px;}
            .card{background:linear-gradient(180deg,rgba(255,255,255,.08),rgba(255,255,255,.03));border:1px solid rgba(255,255,255,.12);border-radius:18px;padding:32px;max-width:520px;text-align:center;box-shadow:0 18px 50px rgba(0,0,0,.32);}
            .card h2{margin:0 0 12px;font-size:28px;}
            .card p{margin:0 0 14px;color:rgba(245,247,250,.72);}
            .btn{display:inline-flex;align-items:center;justify-content:center;padding:12px 22px;border-radius:12px;border:1px solid rgba(255,255,255,.08);background:linear-gradient(90deg,#007AFF,#00FFD1);color:#0a0a0a;font-weight:700;text-decoration:none;box-shadow:0 8px 24px rgba(0,255,209,.18),0 10px 26px rgba(0,122,255,.22);transition:transform .18s ease,box-shadow .18s ease;}
            .btn:hover{transform:translateY(-1px);box-shadow:0 12px 32px rgba(0,255,209,.22),0 16px 36px rgba(0,122,255,.28);}
            code{background:rgba(0,0,0,.35);padding:3px 6px;border-radius:6px;font-size:14px;}
          </style>
        </head>
        <body>
          <div class="card" role="status" aria-live="polite">
            <h2>Welcome to Evara ✨</h2>
            <p>Your payment is successful.</p>
            {% if order_id %}
            <p>Order reference: <code>{{ order_id }}</code></p>
            {% endif %}
            <a class="btn" href="/app/">Go to dashboard</a>
          </div>
        </body>
        </html>
        """,
        order_id=order_id,
    )
