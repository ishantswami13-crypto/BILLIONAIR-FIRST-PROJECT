from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models import (Credit, Customer, Item, PaymentIntent, PaymentTransaction, Sale,
                      ShopProfile, User, UserSession)
from ..utils.invoices import next_invoice_number
from ..utils.pdfs import create_invoice_pdf
from ..payments import get_payments_service
from .auth import token_required

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _user_payload(user: User) -> Dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.normalized_role,
    }


def _parse_cursor(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    value = raw.strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError:
        return None


def _pagination_params(default_limit: int = 100, max_limit: int = 500) -> Tuple[int, Optional[datetime]]:
    try:
        limit = int(request.args.get("limit", default_limit))
    except (TypeError, ValueError):
        limit = default_limit
    limit = max(1, min(limit, max_limit))
    cursor = _parse_cursor(request.args.get("cursor"))
    return limit, cursor


def _format_cursor(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    return value.replace(microsecond=0).isoformat() + "Z"


@api_bp.post("/auth/login")
def login():
    if not request.is_json:
        return jsonify({"error": "Expected JSON payload."}), 400

    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials."}), 401

    token = secrets.token_hex(32)
    now = datetime.utcnow()
    user.last_login_at = now
    session = UserSession(
        user=user,
        session_token=token,
        user_agent=request.headers.get("User-Agent", "api"),
        ip_address=request.remote_addr,
        last_seen_at=now,
    )
    db.session.add(session)
    db.session.commit()

    return jsonify({"token": token, "user": _user_payload(user)})


@api_bp.post("/auth/logout")
@token_required
def logout():
    from flask import g

    session: UserSession = g.api_session
    session.revoked_at = datetime.utcnow()
    db.session.add(session)
    db.session.commit()
    return jsonify({"message": "Logged out."})


@api_bp.get("/ping")
def ping():
    return jsonify({"message": "pong", "timestamp": datetime.utcnow().isoformat()})


@api_bp.get("/profile")
@token_required
def profile():
    profile = ShopProfile.query.get(1)
    if not profile:
        return jsonify({"error": "Profile not configured."}), 404
    default_location = profile.default_location
    return jsonify({
        "shop_name": profile.shop_name or profile.name,
        "currency": profile.currency,
        "timezone": profile.timezone,
        "gst_enabled": bool(profile.gst_enabled),
        "location": {
            "id": default_location.id if default_location else None,
            "name": default_location.name if default_location else None,
            "gstin": default_location.gstin if default_location else None,
        },
    })


@api_bp.get("/items")
@token_required
def items():
    limit, cursor = _pagination_params()
    query = Item.query
    if cursor:
        query = query.filter(func.coalesce(Item.updated_at, Item.created_at) > cursor)
    rows = (
        query.order_by(func.coalesce(Item.updated_at, Item.created_at).asc(), Item.id.asc())
        .limit(limit)
        .all()
    )
    payload = [
        {
            "id": item.id,
            "name": item.name,
            "price": float(item.price or 0),
            "stock": int(item.current_stock or 0),
            "reorder_level": int(item.reorder_level or 5),
            "gst_rate": float(item.gst_rate or 0),
            "updated_at": _format_cursor(item.updated_at or item.created_at),
        }
        for item in rows
    ]
    next_cursor = _format_cursor(rows[-1].updated_at or rows[-1].created_at) if rows else None
    return jsonify({"items": payload, "count": len(payload), "next_cursor": next_cursor})


@api_bp.get("/customers")
@token_required
def customers():
    limit, cursor = _pagination_params()
    query = Customer.query
    if cursor:
        query = query.filter(func.coalesce(Customer.updated_at, Customer.created_at) > cursor)
    rows = (
        query.order_by(func.coalesce(Customer.updated_at, Customer.created_at).asc(), Customer.id.asc())
        .limit(limit)
        .all()
    )
    payload = [
        {
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
            "email": customer.email,
            "gstin": getattr(customer, "gstin", None),
            "updated_at": _format_cursor(customer.updated_at or customer.created_at),
        }
        for customer in rows
    ]
    next_cursor = _format_cursor(rows[-1].updated_at or rows[-1].created_at) if rows else None
    return jsonify({"customers": payload, "count": len(payload), "next_cursor": next_cursor})


@api_bp.get("/sales")
@token_required
def sales():
    limit, cursor = _pagination_params(default_limit=50, max_limit=200)
    query = Sale.query
    if cursor:
        query = query.filter(Sale.date > cursor)
    rows = (
        query.order_by(Sale.date.asc(), Sale.id.asc())
        .limit(limit)
        .all()
    )
    payload = [
        {
            "id": sale.id,
            "invoice_number": sale.invoice_number,
            "date": sale.date.isoformat() if sale.date else None,
            "item": sale.item,
            "quantity": sale.quantity,
            "total": float(sale.net_total or sale.total or 0),
            "payment_method": sale.payment_method,
            "gst_status": sale.gst_status,
        }
        for sale in rows
    ]
    next_cursor = _format_cursor(rows[-1].date) if rows else None
    return jsonify({"sales": payload, "count": len(payload), "next_cursor": next_cursor})


@api_bp.post("/sales")
@token_required
def record_sale():
    if not request.is_json:
        return jsonify({"error": "Expected JSON payload."}), 400

    payload = request.get_json() or {}
    item_id = payload.get("item_id")
    quantity = payload.get("quantity")
    customer_id = payload.get("customer_id")
    customer_name = (payload.get("customer_name") or "").strip()
    payment_method = (payload.get("payment_method") or "cash").lower()
    discount = float(payload.get("discount") or 0)

    if not item_id or not quantity:
        return jsonify({"error": "item_id and quantity are required."}), 400

    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        return jsonify({"error": "quantity must be an integer."}), 400
    if quantity <= 0:
        return jsonify({"error": "quantity must be positive."}), 400

    item = Item.query.get(item_id)
    if not item:
        return jsonify({"error": "Item not found."}), 404

    if item.current_stock is not None and quantity > item.current_stock:
        return jsonify({"error": "Insufficient stock."}), 400

    customer = None
    if customer_id:
        customer = Customer.query.get(customer_id)
    elif customer_name:
        customer = Customer.query.filter_by(name=customer_name).first()
        if not customer:
            customer = Customer(name=customer_name)
            db.session.add(customer)
            db.session.flush()

    subtotal = item.price * quantity
    gst_rate = item.gst_rate or 0
    taxable = max(subtotal - discount, 0)
    tax = round(taxable * (gst_rate / 100), 2)
    net_total = round(taxable + tax, 2)

    if item.current_stock is not None:
        item.current_stock -= quantity

    profile = ShopProfile.query.get(1)
    location_id = profile.default_location.id if profile and profile.default_location else None

    sale = Sale(
        item=item.name,
        quantity=quantity,
        total=net_total,
        customer_id=customer.id if customer else None,
        payment_method=payment_method,
        discount=discount,
        tax=tax,
        net_total=net_total,
        invoice_number=next_invoice_number(),
        location_id=location_id,
    )
    db.session.add(sale)
    db.session.flush()

    if payload.get("sale_type") == "udhar":
        if not customer and not customer_name:
            return jsonify({"error": "Customer required for credit sale."}), 400
        db.session.add(Credit(
            customer_id=customer.id if customer else None,
            customer_name=customer.name if customer else customer_name,
            item=item.name,
            quantity=quantity,
            total=net_total,
            status='unpaid',
            reminder_phone=(customer.phone if customer and customer.phone else None)
        ))

    db.session.commit()
    create_invoice_pdf(sale.id)
    return jsonify({
        "id": sale.id,
        "invoice_number": sale.invoice_number,
        "total": float(net_total),
        "gst_status": sale.gst_status,
    }), 201


@api_bp.get("/payments/providers")
@token_required
def payment_providers():
    service = get_payments_service()
    return jsonify({"providers": service.list_providers()})


@api_bp.post("/payments/intents")
@token_required
def create_payment_intent():
    if not request.is_json:
        return jsonify({"error": "Expected JSON payload."}), 400

    payload = request.get_json() or {}
    try:
        amount = float(payload.get("amount", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "amount must be numeric."}), 400
    if amount <= 0:
        return jsonify({"error": "amount must be greater than zero."}), 400

    sale_id = payload.get("sale_id")
    sale = None
    if sale_id:
        sale = Sale.query.get(sale_id)
        if not sale:
            return jsonify({"error": "Sale not found."}), 404

    provider_name = (payload.get("provider") or "razorpay").lower()
    service = get_payments_service()
    provider = service.get_provider(provider_name)
    if not provider:
        return jsonify({"error": "Unsupported provider."}), 400
    if not provider.enabled:
        return jsonify({"error": f"Provider {provider.display_name} is not configured."}), 400

    profile = ShopProfile.query.get(1)
    currency = (payload.get("currency") or (profile.currency if profile else "INR")).upper()
    reference = payload.get("customer_reference")

    intent = PaymentIntent(
        sale_id=sale.id if sale else None,
        amount=amount,
        currency=currency,
        provider=provider.name,
        status="pending",
        customer_reference=reference,
        meta_info=None,
    )
    db.session.add(intent)
    db.session.flush()

    transaction = PaymentTransaction(
        intent=intent,
        provider=provider.name,
        status="created",
        amount=amount,
        reference=None,
    )
    db.session.add(transaction)
    db.session.commit()

    return jsonify({
        "intent_id": intent.id,
        "status": intent.status,
        "provider": provider.name,
        "amount": amount,
        "currency": currency,
        "transaction_id": transaction.id,
    }), 201
