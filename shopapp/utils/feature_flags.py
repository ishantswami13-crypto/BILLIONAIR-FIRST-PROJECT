from __future__ import annotations

from functools import lru_cache
from typing import Iterable, Mapping, MutableMapping

from flask import current_app, session

from ..plans import PlanDefinition, build_plan_matrix


@lru_cache(maxsize=1)
def _cached_plans() -> MutableMapping[str, PlanDefinition]:
    extras: Mapping[str, Iterable[str]] | None = current_app.config.get("EXTRA_PLAN_FEATURES")
    return build_plan_matrix({k: set(v) for k, v in (extras or {}).items()})


def get_active_plan_slug() -> str:
    return session.get("plan") or current_app.config.get("ACTIVE_PLAN", "pro")


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
