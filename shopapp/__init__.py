from datetime import datetime, timedelta
from decimal import Decimal

from flask import Flask, url_for

from .config import Config
from .extensions import db, migrate, scheduler
from .marketing import marketing_bp
from .admin import admin_bp
from .settings import settings_bp
from .assistant import assistant_bp
from .auth.routes import auth_bp
from .sales.routes import sales_bp
from .reports.routes import reports_bp
from .inventory.routes import inventory_bp
from .expenses.routes import expenses_bp
from .credits import credits_bp
from .customers.routes import customers_bp
from .engagement import bp as engagement_bp
from .webhooks import webhooks_bp
from .cli import register_cli
from .utils.mail import init_mail_settings
from .utils.feature_flags import feature_enabled, get_active_plan, reset_cache as reset_plan_cache
from .utils.flags import flags
from .utils.nudges import send_streak_reminder
from .utils.subscription import get_subscription_context
from .onboarding import onboarding_bp
from .compliance import compliance_bp
from .api import api_bp
from .payments import payments_bp
from .security import can_access, get_current_role
import daily_report
from .credits.tasks import send_credit_reminders
import drive_backup
from sqlalchemy import func, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from .utils.schema import ensure_columns
from .models import FeatureFlag, Plan, PlanFeature, Quest, Setting, ShopLocation, ShopProfile, User, UserRole
from .plans import BASE_FEATURES

LEGACY_COLUMN_REQUIREMENTS = {
    'users': {'password_hash'},
    'items': {'gst_rate', 'reorder_level', 'current_stock'},
    'sales': {'payment_method', 'discount', 'net_total'},
    'settings': {'value'},
}


SCHEMA_PATCHES = {
    "shop_profile": {
        "shop_name": "shop_name VARCHAR(255)",
        "currency": "currency VARCHAR(8) DEFAULT 'INR'",
        "timezone": "timezone VARCHAR(64) DEFAULT 'Asia/Kolkata'",
        "gst_enabled": "gst_enabled BOOLEAN DEFAULT 0",
        "low_stock_threshold": "low_stock_threshold INTEGER DEFAULT 5",
        "opening_cash": "opening_cash REAL DEFAULT 0",
        "logo_path": "logo_path VARCHAR(255)",
        "invoice_prefix": "invoice_prefix VARCHAR(20) DEFAULT 'INV'",
        "primary_color": "primary_color VARCHAR(20)",
        "secondary_color": "secondary_color VARCHAR(20)",
        "signature_path": "signature_path VARCHAR(255)",
        "watermark_path": "watermark_path VARCHAR(255)",
        "plan_slug": "plan_slug VARCHAR(50)",
        "plan_id": "plan_id INTEGER",
        "trial_plan_slug": "trial_plan_slug VARCHAR(50)",
        "trial_started_at": "trial_started_at DATETIME",
        "trial_ends_at": "trial_ends_at DATETIME",
        "trial_cancelled_at": "trial_cancelled_at DATETIME"
    },
    "sales": {
        "invoice_number": "invoice_number VARCHAR(64)",
        "locked": "locked BOOLEAN DEFAULT 0",
        "location_id": "location_id INTEGER",
        "gst_status": "gst_status VARCHAR(20) DEFAULT 'pending'",
        "irn": "irn VARCHAR(64)",
        "ack_no": "ack_no VARCHAR(64)",
        "ack_date": "ack_date DATETIME",
        "signed_invoice_path": "signed_invoice_path VARCHAR(255)",
        "eway_bill_no": "eway_bill_no VARCHAR(64)",
        "eway_valid_upto": "eway_valid_upto DATETIME",
    },
    "audit_log": {
        "resource_type": "resource_type VARCHAR(64)",
        "resource_id": "resource_id INTEGER",
        "before_state": "before_state TEXT",
        "after_state": "after_state TEXT",
        "ip_address": "ip_address VARCHAR(64)",
        "user_agent": "user_agent VARCHAR(255)",
    },
    "users": {
        "phone": "phone VARCHAR(50)",
        "email": "email VARCHAR(255)",
        "last_login_at": "last_login_at DATETIME",
        "last_active_at": "last_active_at DATETIME",
        "streak_count": "streak_count INTEGER DEFAULT 0",
        "xp": "xp INTEGER DEFAULT 0",
        "engagement_opt_out": "engagement_opt_out BOOLEAN DEFAULT 0"
    },
    "user_invites": {
        "invited_by_id": "invited_by_id INTEGER",
        "status": "status VARCHAR(20) DEFAULT 'pending'",
        "last_sent_at": "last_sent_at DATETIME"
    },
    "expenses": {
        "category_id": "category_id INTEGER"
    },
    "credits": {
        "customer_id": "customer_id INTEGER",
        "last_reminder_at": "last_reminder_at DATETIME",
        "reminder_count": "reminder_count INTEGER DEFAULT 0",
        "reminder_opt_out": "reminder_opt_out BOOLEAN DEFAULT 0",
        "reminder_phone": "reminder_phone VARCHAR(50)"
    },
    "items": {
        "created_at": "created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "updated_at DATETIME"
    },
    "customers": {
        "created_at": "created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "updated_at DATETIME"
    },
    "purchase_orders": {
        "status": "status VARCHAR(50) DEFAULT 'draft'",
        "total_cost": "total_cost REAL DEFAULT 0",
        "notes": "notes TEXT",
        "created_at": "created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
        "received_at": "received_at DATETIME"
    },
    "purchase_items": {
        "cost_price": "cost_price REAL"
    },
}

PLAN_PRESETS: dict[str, dict[str, object]] = {
    "free": {
        "name": "Free",
        "price_monthly": Decimal("0"),
        "description": "Single device billing, inventory and daily summaries.",
        "display_order": 0,
        "highlight": False,
        "trial_days": 0,
    },
    "pro": {
        "name": "Pro",
        "price_monthly": Decimal("1499"),
        "description": "Automation, analytics, branding controls and QR connect.",
        "display_order": 1,
        "highlight": True,
        "trial_days": 14,
    },
    "enterprise": {
        "name": "Enterprise",
        "price_monthly": Decimal("4999"),
        "description": "Advanced governance, export bundles and premium support.",
        "display_order": 2,
        "highlight": False,
        "trial_days": 30,
    },
}


def _seed_plans() -> None:
    existing = {
        plan.slug: plan
        for plan in Plan.query.options(joinedload(Plan.features)).all()
    }
    order_cursor = 0
    for slug, features in BASE_FEATURES.items():
        preset = PLAN_PRESETS.get(slug, {})
        plan = existing.get(slug)
        if not plan:
            plan = Plan(slug=slug)
            db.session.add(plan)
            existing[slug] = plan
        plan.name = preset.get("name", slug.title())
        plan.price_monthly = preset.get("price_monthly", Decimal("0"))
        plan.currency = preset.get("currency", "INR")
        plan.description = preset.get("description")
        plan.highlight = bool(preset.get("highlight", False))
        plan.display_order = int(preset.get("display_order", order_cursor))
        plan.trial_days = int(preset.get("trial_days", 0))
        plan.is_active = True
        order_cursor = max(order_cursor, plan.display_order + 1)

        existing_codes = {feature.code for feature in plan.features}
        for code in features:
            if code not in existing_codes:
                plan.features.append(PlanFeature(code=code))
        for feature in list(plan.features):
            if feature.code not in features:
                db.session.delete(feature)
    db.session.commit()
    reset_plan_cache()


def _reset_legacy_schema_if_needed() -> None:
    engine = db.engine
    insp = inspect(engine)
    statements = []

    for table, required_cols in LEGACY_COLUMN_REQUIREMENTS.items():
        if table not in insp.get_table_names():
            continue
        columns = {col['name'] for col in insp.get_columns(table)}
        if not required_cols.issubset(columns):
            statements.append(text(f'DROP TABLE IF EXISTS {table}'))

    if statements:
        with engine.begin() as conn:
            for stmt in statements:
                    conn.execute(stmt)


def _bootstrap_app(app: Flask) -> None:
    _reset_legacy_schema_if_needed()

    engine = db.engine
    for table, columns in SCHEMA_PATCHES.items():
        ensure_columns(engine, table, columns)

    db.create_all()

    with engine.begin() as conn:
        conn.execute(text("UPDATE items SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)"))
        conn.execute(text("UPDATE customers SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)"))

    _seed_plans()
    _seed_engagement_objects()

    profile = ShopProfile.query.get(1)
    if profile is None:
        profile = ShopProfile(
            id=1,
            name='My Shop',
            shop_name='My Shop',
            address='',
            phone='',
            gst='',
            invoice_prefix='INV',
            primary_color='#0A2540',
            secondary_color='#62b5ff',
            currency='INR',
            timezone='Asia/Kolkata',
            gst_enabled=False,
            low_stock_threshold=5,
            opening_cash=0,
            plan_slug='pro',
        )
        db.session.add(profile)
    else:
        if not getattr(profile, 'plan_slug', None):
            profile.plan_slug = 'pro'
        if not getattr(profile, 'shop_name', None):
            profile.shop_name = profile.name or 'My Shop'
        if not getattr(profile, 'currency', None):
            profile.currency = 'INR'
        if not getattr(profile, 'timezone', None):
            profile.timezone = 'Asia/Kolkata'
        if getattr(profile, 'gst_enabled', None) is None:
            profile.gst_enabled = False
        if getattr(profile, 'low_stock_threshold', None) is None:
            profile.low_stock_threshold = 5
        if getattr(profile, 'opening_cash', None) is None:
            profile.opening_cash = 0

    if profile:
        plan_lookup_slug = profile.plan_slug or app.config.get("ACTIVE_PLAN", "pro")
        plan_obj = Plan.query.filter_by(slug=plan_lookup_slug).first()
        if plan_obj:
            profile.plan_id = plan_obj.id
            if not profile.plan_slug:
                profile.plan_slug = plan_obj.slug
        if not getattr(profile, "locations", None):
            default_location = ShopLocation(
                profile=profile,
                name=profile.shop_name or profile.name or "Head Office",
                gstin=profile.gst or None,
                address=profile.address or "",
                is_default=True,
            )
            db.session.add(default_location)

    cfg = app.config
    admin_username = cfg.get('DEFAULT_ADMIN_USERNAME', 'admin')
    admin_email = cfg.get('DEFAULT_ADMIN_EMAIL', 'admin@example.com')
    admin_password = cfg.get('DEFAULT_ADMIN_PASSWORD', 'admin123')

    admin = User.query.filter_by(username=admin_username).first()
    if not admin:
        admin = User(username=admin_username, email=admin_email, role=UserRole.owner)
        admin.set_password(admin_password)
        admin.email_verified = True
        db.session.add(admin)
    else:
        admin.role = UserRole.owner

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()


def _seed_engagement_objects() -> None:
    quest_defaults: tuple[dict[str, object], ...] = (
        {
            "code": "FIRST_TASK",
            "title": "Your First Win",
            "description": "Complete your first core action.",
            "xp_reward": 25,
            "is_recurring": False,
            "daily_limit": 1,
        },
        {
            "code": "DAILY_USE",
            "title": "Daily Login",
            "description": "Open the app and perform a core action.",
            "xp_reward": 10,
            "is_recurring": True,
            "daily_limit": 1,
        },
        {
            "code": "SHARE_LINK",
            "title": "Share Your Link",
            "description": "Share invite link with a friend.",
            "xp_reward": 20,
            "is_recurring": False,
            "daily_limit": 3,
        },
        {
            "code": "COMPLETE_3",
            "title": "Finish 3 Actions",
            "description": "Do the core action 3 times today.",
            "xp_reward": 30,
            "is_recurring": True,
            "daily_limit": 1,
        },
    )

    for spec in quest_defaults:
        code = spec["code"]
        quest = Quest.query.filter_by(code=code).first()
        if quest:
            continue
        quest = Quest(
            code=spec["code"],
            title=spec["title"],
            description=spec["description"],
            xp_reward=spec["xp_reward"],
            is_recurring=spec["is_recurring"],
            daily_limit=spec["daily_limit"],
        )
        db.session.add(quest)

    flag_defaults: dict[str, bool] = {
        "show_referrals": True,
        "show_quests": True,
    }

    for key, enabled in flag_defaults.items():
        flag = FeatureFlag.query.filter_by(key=key).first()
        if not flag:
            db.session.add(FeatureFlag(key=key, enabled=enabled))
        elif flag.enabled != enabled:
            flag.enabled = enabled

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()


def create_app(config_object: type[Config] | None = None) -> Flask:
    app = Flask(__name__)
    cfg = config_object or Config
    app.config.from_object(cfg)
    reset_plan_cache()

    @app.context_processor
    def inject_globals() -> dict[str, object | None]:
        plan = get_active_plan()
        subscription = get_subscription_context()
        profile = ShopProfile.query.get(1)
        theme_setting = Setting.query.filter_by(key="ui_theme").first()
        theme_value = (theme_setting.value if theme_setting and theme_setting.value else "").strip().lower()
        body_class = "theme-purple" if theme_value == "purple" else "theme-mint"
        return {
            "GA_MEASUREMENT_ID": app.config.get("GA_MEASUREMENT_ID"),
            "MIXPANEL_TOKEN": app.config.get("MIXPANEL_TOKEN"),
            "ACTIVE_PLAN": plan.slug if plan else None,
            "active_plan": plan.slug if plan else None,
            "SUBSCRIPTION": subscription,
            "subscription": subscription,
            "shop_profile": profile,
            "body_class": body_class,
            "app_version": app.config.get("APP_VERSION"),
            "encryption_notice": app.config.get("DATA_ENCRYPTION_NOTICE"),
            "feature_enabled": feature_enabled,
            "can_access": can_access,
            "current_role": get_current_role,
            "flags": flags,
        }

    app.jinja_env.globals["feature_enabled"] = feature_enabled
    app.jinja_env.globals["active_plan"] = lambda: (get_active_plan().slug if get_active_plan() else None)
    app.jinja_env.globals["can_access"] = can_access
    app.jinja_env.globals["current_role"] = get_current_role
    app.jinja_env.globals["flags"] = flags

    db.init_app(app)
    migrate.init_app(app, db)
    init_mail_settings(app)
    register_cli(app)

    app.register_blueprint(marketing_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(assistant_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(onboarding_bp)
    app.register_blueprint(compliance_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(sales_bp, url_prefix='/app')
    app.add_url_rule('/app/', endpoint='index', view_func=sales_bp.view_functions['index'])
    app.register_blueprint(reports_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(credits_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(engagement_bp)
    app.register_blueprint(webhooks_bp)

    def _schedule_job(fn, **trigger_kwargs):
        def runner():
            with app.app_context():
                fn()
        scheduler.add_job(runner, **trigger_kwargs)

    with app.app_context():
        _bootstrap_app(app)
        if not getattr(app, 'apscheduler', None):
            def _run_streak_nudges() -> None:
                today = datetime.utcnow().date()
                yesterday = today - timedelta(days=1)
                try:
                    link = url_for("engagement.hub", _external=True)
                except RuntimeError:
                    link = app.config.get("ENGAGEMENT_APP_LINK") or "https://yourapp.example/app"

                users = (
                    User.query.filter(
                        User.engagement_opt_out.is_(False),
                        User.phone.isnot(None),
                        User.phone != "",
                        User.streak_count >= 1,
                        User.last_active_at.isnot(None),
                    )
                    .filter(func.date(User.last_active_at) == yesterday)
                    .all()
                )

                for user in users:
                    try:
                        send_streak_reminder(user, link)
                    except Exception:
                        continue

            _schedule_job(_run_streak_nudges, trigger='cron', hour=17, minute=0)
            _schedule_job(daily_report.send_daily_report, trigger='cron', hour=22, minute=0)
            _schedule_job(send_credit_reminders, trigger='cron', hour=18, minute=0)
            _schedule_job(drive_backup.backup_to_drive, trigger='cron', hour=23, minute=59)
            scheduler.start()
            app.apscheduler = scheduler

    return app

