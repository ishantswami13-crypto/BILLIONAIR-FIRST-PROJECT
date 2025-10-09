from flask import Flask

from .config import Config
from .extensions import db, migrate, scheduler
from .marketing import marketing_bp
from .admin import admin_bp
from .settings import settings_bp
from .auth.routes import auth_bp
from .sales.routes import sales_bp
from .reports.routes import reports_bp
from .inventory.routes import inventory_bp
from .expenses.routes import expenses_bp
from .customers.routes import customers_bp
from .cli import register_cli
from .utils.mailer import init_mail_settings
from .utils.feature_flags import feature_enabled, get_active_plan, reset_cache as reset_plan_cache
import daily_report
import drive_backup
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from .utils.schema import ensure_columns

LEGACY_COLUMN_REQUIREMENTS = {
    'users': {'password_hash'},
    'items': {'gst_rate', 'reorder_level', 'current_stock'},
    'sales': {'payment_method', 'discount', 'net_total'},
    'settings': {'value'},
}


SCHEMA_PATCHES = {
    "shop_profile": {
        "logo_path": "logo_path VARCHAR(255)",
        "invoice_prefix": "invoice_prefix VARCHAR(20) DEFAULT 'INV'",
        "primary_color": "primary_color VARCHAR(20)",
        "secondary_color": "secondary_color VARCHAR(20)",
        "signature_path": "signature_path VARCHAR(255)",
        "watermark_path": "watermark_path VARCHAR(255)",
    },
    "sales": {
        "invoice_number": "invoice_number VARCHAR(64)",
        "locked": "locked BOOLEAN DEFAULT 0",
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
        "email": "email VARCHAR(255)"
    },
    "expenses": {
        "category_id": "category_id INTEGER"
    },
}


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
    from .models import ShopProfile, User

    _reset_legacy_schema_if_needed()

    engine = db.engine
    for table, columns in SCHEMA_PATCHES.items():
        ensure_columns(engine, table, columns)

    db.create_all()

    if ShopProfile.query.get(1) is None:
        profile = ShopProfile(id=1, name='My Shop', address='', phone='', gst='', invoice_prefix='INV', primary_color='#0A2540', secondary_color='#62b5ff')
        db.session.add(profile)

    cfg = app.config
    admin_username = cfg.get('DEFAULT_ADMIN_USERNAME', 'admin')
    admin_email = cfg.get('DEFAULT_ADMIN_EMAIL', 'admin@example.com')
    admin_password = cfg.get('DEFAULT_ADMIN_PASSWORD', 'admin123')

    admin = User.query.filter_by(username=admin_username).first()
    if not admin:
        admin = User(username=admin_username, email=admin_email)
        admin.set_password(admin_password)
        admin.email_verified = True
        db.session.add(admin)

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
        return {
            "GA_MEASUREMENT_ID": app.config.get("GA_MEASUREMENT_ID"),
            "MIXPANEL_TOKEN": app.config.get("MIXPANEL_TOKEN"),
            "ACTIVE_PLAN": plan.slug if plan else None,
            "feature_enabled": feature_enabled,
        }

    app.jinja_env.globals["feature_enabled"] = feature_enabled
    app.jinja_env.globals["active_plan"] = lambda: (get_active_plan().slug if get_active_plan() else None)

    db.init_app(app)
    migrate.init_app(app, db)
    init_mail_settings(app)
    register_cli(app)

    app.register_blueprint(marketing_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(sales_bp, url_prefix='/app')
    app.register_blueprint(reports_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(customers_bp)

    def _schedule_job(fn, **trigger_kwargs):
        def runner():
            with app.app_context():
                fn()
        scheduler.add_job(runner, **trigger_kwargs)

    with app.app_context():
        _bootstrap_app(app)
        if not getattr(app, 'apscheduler', None):
            _schedule_job(daily_report.send_daily_report, trigger='cron', hour=22, minute=0)
            _schedule_job(drive_backup.backup_to_drive, trigger='cron', hour=23, minute=59)
            scheduler.start()
            app.apscheduler = scheduler

    return app

