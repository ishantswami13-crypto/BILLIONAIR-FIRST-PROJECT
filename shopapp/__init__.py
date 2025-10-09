from flask import Flask

from .config import Config
from .extensions import db, migrate, scheduler
from .marketing import marketing_bp
from .admin import admin_bp
from .auth.routes import auth_bp
from .sales.routes import sales_bp
from .reports.routes import reports_bp
from .inventory.routes import inventory_bp
from .expenses.routes import expenses_bp
from .customers.routes import customers_bp
from .cli import register_cli
from .utils.mailer import init_mail_settings
import daily_report
import drive_backup
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError


LEGACY_COLUMN_REQUIREMENTS = {
    'users': {'password_hash'},
    'items': {'gst_rate', 'reorder_level', 'current_stock'},
    'sales': {'payment_method', 'discount', 'net_total'},
    'settings': {'value'},
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
    db.create_all()

    if ShopProfile.query.get(1) is None:
        profile = ShopProfile(id=1, name='My Shop', address='', phone='', gst='')
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

    @app.context_processor
    def inject_analytics() -> dict[str, str | None]:
        return {
            "GA_MEASUREMENT_ID": app.config.get("GA_MEASUREMENT_ID"),
            "MIXPANEL_TOKEN": app.config.get("MIXPANEL_TOKEN"),
        }

    db.init_app(app)
    migrate.init_app(app, db)
    init_mail_settings(app)
    register_cli(app)

    app.register_blueprint(marketing_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(sales_bp, url_prefix='/app')
    app.register_blueprint(reports_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(customers_bp)

    with app.app_context():
        _bootstrap_app(app)
        if not getattr(app, 'apscheduler', None):
            scheduler.add_job(daily_report.send_daily_report, trigger='cron', hour=22, minute=0)
            scheduler.add_job(drive_backup.backup_to_drive, trigger='cron', hour=23, minute=59)
            scheduler.start()
            app.apscheduler = scheduler

    return app

