from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import current_app
from sqlalchemy.orm import joinedload

from ..models import Plan, ShopProfile


def _serialize_price(amount: Optional[object], currency: str | None) -> Dict[str, object]:
    value = float(amount or 0)
    currency_code = (currency or "INR").upper()
    symbol = "₹" if currency_code == "INR" else currency_code
    if value <= 0:
        display = "Free"
    else:
        display = f"{symbol}{value:,.0f} / mo"
    return {
        "value": value,
        "currency": currency_code,
        "display": display,
    }


def _serialize_plan(plan: Plan) -> Dict[str, Any]:
    features = sorted({feature.code for feature in plan.features})
    return {
        "id": plan.id,
        "slug": plan.slug,
        "name": plan.name,
        "description": plan.description or "",
        "price": _serialize_price(plan.price_monthly, plan.currency),
        "highlight": plan.highlight,
        "display_order": plan.display_order or 0,
        "is_active": plan.is_active,
        "trial_days": plan.trial_days or 0,
        "features": features,
    }


def _collect_plans() -> List[Dict[str, Any]]:
    plans = (
        Plan.query.options(joinedload(Plan.features))
        .filter(Plan.is_active.is_(True))
        .order_by(Plan.display_order.asc(), Plan.id.asc())
        .all()
    )
    return [_serialize_plan(plan) for plan in plans]


def _profile_context(profile: ShopProfile | None) -> Dict[str, Any]:
    if not profile:
        fallback_slug = current_app.config.get("ACTIVE_PLAN", "pro")
        return {
            "active_plan_slug": fallback_slug,
            "base_plan_slug": fallback_slug,
            "trial": {
                "active": False,
                "plan_slug": None,
                "days_remaining": None,
                "ends_at": None,
            },
        }

    active_slug = profile.active_plan_slug()
    base_slug = profile.plan_slug or (profile.plan.slug if profile.plan else None) or active_slug
    trial_active = profile.trial_active
    return {
        "active_plan_slug": active_slug,
        "base_plan_slug": base_slug,
        "trial": {
            "active": trial_active,
            "plan_slug": profile.trial_plan_slug if trial_active else None,
            "days_remaining": profile.trial_days_remaining if trial_active else None,
            "ends_at": profile.trial_ends_at if trial_active else None,
        },
    }


def get_subscription_context() -> Dict[str, Any]:
    profile = ShopProfile.query.options(joinedload(ShopProfile.plan)).get(1)
    context = _profile_context(profile)
    context["plans"] = _collect_plans()
    return context
