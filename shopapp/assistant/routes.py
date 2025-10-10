from __future__ import annotations

from datetime import datetime, timedelta
import json

from flask import Blueprint, jsonify, make_response, render_template, request, session as flask_session
from sqlalchemy import func

from ..extensions import db
from ..models import (AssistantMessage, AssistantSession, Credit, Expense,
                      Item, Sale)
from ..utils.analytics import load_analytics
from ..utils.decorators import login_required

assistant_bp = Blueprint("assistant", __name__, url_prefix="/assistant")

OUTSTANDING_STATUSES = ("unpaid", "adjusted")


def _today_bounds() -> tuple[datetime, datetime]:
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def _today_summary() -> dict[str, float]:
    start, end = _today_bounds()
    revenue, count = (
        db.session.query(
            func.coalesce(func.sum(Sale.net_total), 0),
            func.count(Sale.id),
        )
        .filter(Sale.date.between(start, end))
        .first()
    )
    expenses = (
        db.session.query(func.coalesce(func.sum(Expense.amount), 0))
        .filter(Expense.date.between(start.date(), end.date()))
        .scalar()
        or 0
    )
    return {
        "revenue": float(revenue or 0),
        "transactions": int(count or 0),
        "expenses": float(expenses or 0),
        "profit": float(revenue or 0) - float(expenses or 0),
    }


def _low_stock(limit: int = 5) -> list[Item]:
    return (
        Item.query
        .filter(Item.current_stock <= func.coalesce(Item.reorder_level, 5))
        .order_by(Item.current_stock.asc(), Item.name.asc())
        .limit(limit)
        .all()
    )


def _outstanding_credit() -> dict[str, float]:
    total, count = (
        db.session.query(
            func.coalesce(func.sum(Credit.total), 0),
            func.count(Credit.id),
        )
        .filter(Credit.status.in_(OUTSTANDING_STATUSES))
        .first()
    )
    return {"amount": float(total or 0), "count": int(count or 0)}


def _generate_reply(message: str) -> str:
    text = (message or "").strip().lower()
    analytics = load_analytics(days=90)
    today = _today_summary()
    credit = _outstanding_credit()

    if not text:
        return "Ask me about revenue, expenses, profit, inventory, or outstanding credits."

    if "revenue" in text or "sales" in text:
        latest = analytics["daily"][-1] if analytics["daily"] else None
        if latest:
            return (
                f"Today's revenue sits at Rs {today['revenue']:.2f} across {today['transactions']} transactions. "
                f"Over the last recorded day ({latest['label']}) you booked Rs {latest['revenue']:.2f}."
            )
        return "No sales recorded yet for the selected range."

    if "expense" in text or "spend" in text:
        top_cats = analytics["categories"][:3]
        cat_summary = ", ".join(f"{row['name']} ({row['share']}%)" for row in top_cats) if top_cats else "no recorded categories"
        return (
            f"Today's expenses total Rs {today['expenses']:.2f}. "
            f"Top spend categories this period: {cat_summary}."
        )

    if "profit" in text:
        summary = analytics["summary"]
        return (
            f"Gross profit today is Rs {today['profit']:.2f}. "
            f"Over the last {len(analytics['daily'])} tracked days the business generated "
            f"Rs {summary['total_profit']:.2f} in profit."
        )

    if "inventory" in text or "stock" in text:
        low_items = _low_stock()
        if not low_items:
            return "All inventory is comfortably above reorder levels."
        details = ", ".join(f"{item.name} ({item.current_stock} left)" for item in low_items)
        return f"Watch these items: {details}. Consider replenishing soon."

    if "credit" in text or "udhar" in text:
        return (
            f"There are {credit['count']} outstanding credit entries totalling "
            f"Rs {credit['amount']:.2f}. Open `/credits` to review or trigger reminders."
        )

    if "help" in text or "what can you do" in text:
        return (
            "Try asking:\n"
            "- What's today's revenue?\n"
            "- Show expense breakdown\n"
            "- Any low stock items?\n"
            "- Outstanding credit amount?"
        )

    summary = analytics["summary"]
    return (
        f"I couldn't find a specific metric, but here's a snapshot:\n"
        f"- Today: revenue Rs {today['revenue']:.2f}, profit Rs {today['profit']:.2f}\n"
        f"- Last {len(analytics['daily'])} days: revenue Rs {summary['total_revenue']:.2f}, "
        f"profit Rs {summary['total_profit']:.2f}\n"
        f"- Outstanding credit: Rs {credit['amount']:.2f} across {credit['count']} entries."
    )


@assistant_bp.route("/", methods=["GET"])
@login_required
def chat_home():
    chat_session = AssistantSession(user=flask_session.get("user"))
    db.session.add(chat_session)
    db.session.commit()
    return render_template(
        "assistant/chat.html",
        chat_session=chat_session,
        messages=[],
    )


@assistant_bp.route("/api/message", methods=["POST"])
@login_required
def api_message():
    payload = request.get_json() or {}
    session_id = payload.get("session_id")
    content = (payload.get("message") or "").strip()
    if not session_id or not content:
        return jsonify({"error": "Missing session_id or message"}), 400

    chat_session = AssistantSession.query.get_or_404(int(session_id))
    user_msg = AssistantMessage(session=chat_session, role="user", content=content)
    db.session.add(user_msg)

    reply = _generate_reply(content)
    assistant_msg = AssistantMessage(session=chat_session, role="assistant", content=reply)
    db.session.add(assistant_msg)
    db.session.commit()

    return jsonify({
        "messages": [
            {
                "role": "user",
                "content": content,
                "created_at": user_msg.created_at.isoformat()
            },
            {
                "role": "assistant",
                "content": reply,
                "created_at": assistant_msg.created_at.isoformat()
            }
        ]
    })


@assistant_bp.route("/<int:session_id>/export", methods=["GET"])
@login_required
def export_session(session_id: int):
    chat_session = AssistantSession.query.get_or_404(session_id)
    history = [
        {
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at.isoformat()
        }
        for msg in sorted(chat_session.messages, key=lambda m: m.created_at)
    ]
    response = make_response(json.dumps({
        "session_id": chat_session.id,
        "user": chat_session.user,
        "created_at": chat_session.created_at.isoformat(),
        "messages": history,
    }, indent=2))
    response.headers["Content-Type"] = "application/json"
    response.headers["Content-Disposition"] = f"attachment; filename=assistant_session_{session_id}.json"
    return response
