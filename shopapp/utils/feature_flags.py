from __future__ import annotations

from functools import lru_cache
from typing import Iterable, Mapping, MutableMapping

from flask import current_app, session
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..plans import BASE_FEATURES, PlanDefinition, build_plan_matrix
from ..models import Plan, PlanFeature, ShopProfile


@lru_cache(maxsize=1)
def _cached_plans() -> MutableMapping[str, PlanDefinition]:
    definitions: MutableMapping[str, PlanDefinition] = {}
    db_plans = (
        Plan.query.options(joinedload(Plan.features))
        .filter(Plan.is_active.is_(True))
        .order_by(Plan.display_order.asc(), Plan.id.asc())
        .all()
    )
    if db_plans:
        for plan in db_plans:
            codes = {feature.code for feature in plan.features}
            definitions[plan.slug] = PlanDefinition(slug=plan.slug, name=plan.name or plan.slug.title(), features=codes)
    if not definitions:
        extras: Mapping[str, Iterable[str]] | None = current_app.config.get("EXTRA_PLAN_FEATURES")
        definitions = build_plan_matrix({k: set(v) for k, v in (extras or {}).items()})
    return definitions


def get_active_plan_slug() -> str:
    cached = session.get("plan")
    if cached:
        return cached
    profile = ShopProfile.query.get(1)
    if profile:
        slug = profile.active_plan_slug()
        if slug:
            return slug
    return current_app.config.get("ACTIVE_PLAN", "pro")


def get_active_plan() -> PlanDefinition:
    plans = _cached_plans()
    slug = get_active_plan_slug()
    return plans.get(slug) or plans.get("pro")


def feature_enabled(feature: str, plan: PlanDefinition | None = None) -> bool:
    plan = plan or get_active_plan()
    if not plan:
        return True
    return feature in plan.features


def reset_cache() -> None:
    _cached_plans.cache_clear()
