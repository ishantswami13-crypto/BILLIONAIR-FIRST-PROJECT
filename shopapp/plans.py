from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, MutableMapping, Set


@dataclass(frozen=True)
class PlanDefinition:
    slug: str
    name: str
    features: Set[str]


BASE_FEATURES: Mapping[str, Set[str]] = {
    "free": {
        "core.dashboard",
        "core.pos",
        "core.inventory",
        "core.customers",
        "core.reports-lite",
    },
    "pro": {
        "core.dashboard",
        "core.pos",
        "core.inventory",
        "core.customers",
        "core.reports",
        "invoices.gst",
        "branding.customisation",
        "analytics.profit_insights",
        "analytics.expense_categories",
        "automation.voice_pos",
        "automation.whatsapp_reminders",
        "assistant.analytics_chat",
        "connect.qr_codes",
        "ui.glassmorphism",
        "authority.banner",
    },
    "enterprise": {
        "core.dashboard",
        "core.pos",
        "core.inventory",
        "core.customers",
        "core.reports",
        "invoices.gst",
        "branding.customisation",
        "analytics.profit_insights",
        "analytics.expense_categories",
        "analytics.ltv_leaderboard",
        "analytics.heatmap",
        "automation.voice_pos",
        "automation.whatsapp_reminders",
        "assistant.analytics_chat",
        "assistant.data_exports",
        "connect.webhooks",
        "connect.role_based_access",
        "connect.qr_codes",
        "ui.glassmorphism",
        "ui.animated_dashboards",
        "authority.banner",
        "audit.export_bundle",
        "backup.retention",
    },
}


def build_plan_matrix(extra: Mapping[str, Set[str]] | None = None) -> MutableMapping[str, PlanDefinition]:
    """Return plan definitions, merging any runtime extras."""

    merged = {}
    extras = extra or {}

    for slug, features in BASE_FEATURES.items():
        merged_set = set(features) | set(extras.get(slug, set()))
        merged[slug] = PlanDefinition(slug=slug, name=slug.title(), features=merged_set)

    for slug, features in extras.items():
        if slug not in merged:
            merged[slug] = PlanDefinition(slug=slug, name=slug.title(), features=set(features))

    return merged
