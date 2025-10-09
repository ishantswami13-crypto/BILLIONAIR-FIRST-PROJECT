# Feature Flags & Plan Gating

The application now centralises plan-aware feature toggles. This document describes how to use and extend the system.

## Overview
- Plans are defined in `shopapp/plans.py` via `BASE_FEATURES`.
- Runtime overrides live in `Config.EXTRA_PLAN_FEATURES` (extend via environment if needed).
- The active plan comes from `session['plan']` and falls back to `Config.ACTIVE_PLAN`.
- Templates can call `feature_enabled("feature.key")` or inspect `ACTIVE_PLAN`.
- Back-end code can import `feature_enabled` or `get_active_plan` from `shopapp.utils.feature_flags`.

## Adding a new feature flag
1. Choose a namespaced key, e.g. `analytics.sales_heatmap`.
2. Add it to the relevant sets in `BASE_FEATURES`.
3. Gate code with:
   ```python
   from shopapp.utils.feature_flags import feature_enabled

   if feature_enabled("analytics.sales_heatmap"):
       ...
   ```
4. Gate templates with:
   ```jinja2
   {% if feature_enabled('analytics.sales_heatmap') %}
     ...
   {% endif %}
   ```

## Overriding features per environment
Set `EXTRA_PLAN_FEATURES` in your config (e.g. inside `create_app` before serving requests) or via environment parsing to add/remove flags at runtime.
