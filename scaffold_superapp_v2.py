import os
import pathlib
import textwrap

FILES = {
    "requirements.txt": """\
Flask==3.0.3
Flask-SQLAlchemy==3.1.1
Flask-Migrate==4.0.7
Flask-JWT-Extended==4.6.0
python-dotenv==1.0.1
qrcode==7.4.2
pillow==10.4.0
passlib[bcrypt]==1.7.4
itsdangerous==2.2.0
# psycopg2-binary==2.9.10  # uncomment when moving to Postgres
""",
    ".env.example": """\
FLASK_ENV=development
SECRET_KEY=change-this
JWT_SECRET_KEY=change-this-too
DATABASE_URL=sqlite:///instance/dev.sqlite3
PSP_PROVIDER=mock
FEATURE_UPI=1
FEATURE_PAYROLL=0
""",
    "manage.py": """\
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
""",
    "README.md": """\
# SuperApp v2 — Flask + SQLAlchemy + JWT

## Quick Start
1) Create venv & install:


python -m venv .venv

Windows:

.venv\\Scripts\\activate

macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

2) Copy env:


cp .env.example .env

3) Run:


python manage.py

4) Flow (JWT):
- POST /api/auth/register -> get token
- Use Authorization: Bearer <token>
- POST /api/merchant/stores
- POST /api/inventory/products
- POST /api/sales/customers
- POST /api/sales/invoice
- POST /api/payments/collect -> upi_uri + qr base64
- POST /api/payments/webhook/mock-paid
""",
    "app/__init__.py": """\
from flask import Flask
from .config import Config
from .extensions import db, migrate, jwt
from .api import register_api, register_errors
import os


def create_app(config_object: type[Config] | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    app.config.from_object(config_object or Config)
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    register_api(app)
    register_errors(app)

    @app.get("/health")
    def health():
        return {"status": "ok"}, 200

    return app
""",
    "app/config.py": """\
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "devkey")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "devjwt")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///instance/dev.sqlite3")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PSP_PROVIDER = os.getenv("PSP_PROVIDER", "mock")
    FEATURE_FLAGS = {
        "UPI": bool(int(os.getenv("FEATURE_UPI", "1"))),
        "PAYROLL": bool(int(os.getenv("FEATURE_PAYROLL", "0"))),
    }
""",
    "app/extensions.py": """\
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
""",
    "app/api.py": """\
from flask import Flask, jsonify


def register_api(app: Flask):
    from .blueprints.auth.routes import bp as auth_bp
    from .blueprints.merchant.routes import bp as merchant_bp
    from .blueprints.inventory.routes import bp as inventory_bp
    from .blueprints.sales.routes import bp as sales_bp
    from .blueprints.payments.routes import bp as payments_bp
    from .blueprints.expenses.routes import bp as expenses_bp
    from .blueprints.reports.routes import bp as reports_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(merchant_bp, url_prefix="/api/merchant")
    app.register_blueprint(inventory_bp, url_prefix="/api/inventory")
    app.register_blueprint(sales_bp, url_prefix="/api/sales")
    app.register_blueprint(payments_bp, url_prefix="/api/payments")
    app.register_blueprint(expenses_bp, url_prefix="/api/expenses")
    app.register_blueprint(reports_bp, url_prefix="/api/reports")


def register_errors(app: Flask):
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "bad request"}), 400

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "server error"}), 500
""",
    "app/utils/feature_flags.py": """\
from flask import current_app


def is_enabled(flag: str) -> bool:
    return current_app.config.get("FEATURE_FLAGS", {}).get(flag, False)
""",
    "app/utils/security.py": """\
from passlib.hash import bcrypt


def hash_password(plain: str) -> str:
    return bcrypt.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.verify(plain, hashed)
    except Exception:
        return False
""",
    "app/models/__init__.py": """\
from .core import Org, User, Store
from .catalog import Product
from .sales import Customer, Invoice, InvoiceItem, Payment
""",
    "app/models/core.py": """\
from datetime import datetime
from ..extensions import db


class Org(db.Model):
    __tablename__ = "orgs"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Store(db.Model):
    __tablename__ = "stores"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("orgs.id"), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    address = db.Column(db.String(255))
    city = db.Column(db.String(80))
    state = db.Column(db.String(80))
    pincode = db.Column(db.String(12))


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("orgs.id"), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default="owner")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
""",
    "app/models/catalog.py": """\
from ..extensions import db


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("orgs.id"), nullable=False)
    sku = db.Column(db.String(120), index=True)
    name = db.Column(db.String(255), nullable=False)
    unit = db.Column(db.String(16), default="pcs")
    price = db.Column(db.Numeric(12, 2), default=0)
    tax_rate = db.Column(db.Numeric(5, 2), default=0)
    opening_stock = db.Column(db.Numeric(12, 3), default=0)
""",
    "app/models/sales.py": """\
from datetime import datetime, date
from ..extensions import db


class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("orgs.id"), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(20))
    gstin = db.Column(db.String(20))


class Invoice(db.Model):
    __tablename__ = "invoices"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("orgs.id"), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"))
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"))
    number = db.Column(db.String(40), index=True)
    date = db.Column(db.Date, default=date.today)
    subtotal = db.Column(db.Numeric(12, 2), default=0)
    tax_total = db.Column(db.Numeric(12, 2), default=0)
    total = db.Column(db.Numeric(12, 2), default=0)
    status = db.Column(db.String(20), default="due")


class InvoiceItem(db.Model):
    __tablename__ = "invoice_items"
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"))
    description = db.Column(db.String(255))
    qty = db.Column(db.Numeric(12, 3), default=1)
    rate = db.Column(db.Numeric(12, 2), default=0)
    tax_rate = db.Column(db.Numeric(5, 2), default=0)
    line_total = db.Column(db.Numeric(12, 2), default=0)


class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"))
    org_id = db.Column(db.Integer, db.ForeignKey("orgs.id"), nullable=False)
    method = db.Column(db.String(20), default="UPI")
    amount = db.Column(db.Numeric(12, 2), default=0)
    ref = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
""",
    "app/services/upi.py": """\
\"\"\"UPI Provider adapter. Starts with MOCK for local dev.
Switch to Razorpay/Cashfree later by implementing same interface.
\"\"\"
import base64
import io
import qrcode


class MockUPIProvider:
    @staticmethod
    def create_collect_request(payee_vpa: str, amount: float, txn_note: str, invoice_number: str) -> dict:
        upi_uri = f"upi://pay?pa={payee_vpa}&pn=Merchant&am={amount:.2f}&cu=INR&tn={txn_note}&tr={invoice_number}"
        img = qrcode.make(upi_uri)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return {"upi_uri": upi_uri, "qr_png_base64": b64}


def get_upi_provider(name: str):
    name = (name or "mock").lower()
    return MockUPIProvider()
""",
    "app/blueprints/__init__.py": "",
    "app/blueprints/auth/__init__.py": "",
    "app/blueprints/merchant/__init__.py": "",
    "app/blueprints/inventory/__init__.py": "",
    "app/blueprints/sales/__init__.py": "",
    "app/blueprints/payments/__init__.py": "",
    "app/blueprints/expenses/__init__.py": "",
    "app/blueprints/reports/__init__.py": "",
    "app/blueprints/auth/routes.py": """\
from flask import Blueprint, request
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from ...extensions import db
from ...models.core import Org, User
from ...utils.security import hash_password, verify_password

bp = Blueprint("auth", __name__)


@bp.post("/register")
def register():
    data = request.get_json() or {}
    org_name = data.get("org_name") or "My Org"
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return {"error": "email and password required"}, 400
    if db.session.scalar(db.select(User).filter_by(email=email)):
        return {"error": "email already exists"}, 400

    org = Org(name=org_name)
    db.session.add(org)
    db.session.flush()

    user = User(org_id=org.id, email=email, password_hash=hash_password(password), role="owner")
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity={"user_id": user.id, "org_id": org.id})
    return {"access_token": token, "org_id": org.id, "user_id": user.id}, 201


@bp.post("/login")
def login():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")
    user = db.session.scalar(db.select(User).filter_by(email=email))
    if not user or not verify_password(password, user.password_hash):
        return {"error": "invalid credentials"}, 401
    token = create_access_token(identity={"user_id": user.id, "org_id": user.org_id})
    return {"access_token": token}


@bp.get("/me")
@jwt_required()
def me():
    ident = get_jwt_identity() or {}
    return {"identity": ident}
""",
    "app/blueprints/merchant/routes.py": """\
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ...extensions import db
from ...models.core import Store

bp = Blueprint("merchant", __name__)


@bp.post("/stores")
@jwt_required()
def create_store():
    ident = get_jwt_identity() or {}
    org_id = ident.get("org_id")
    data = request.get_json() or {}
    store = Store(org_id=org_id, name=data.get("name", "Main Store"), address=data.get("address"))
    db.session.add(store)
    db.session.commit()
    return {"id": store.id, "name": store.name}, 201


@bp.get("/stores")
@jwt_required()
def list_stores():
    ident = get_jwt_identity() or {}
    org_id = ident.get("org_id")
    rows = db.session.scalars(db.select(Store).filter_by(org_id=org_id)).all()
    return {"stores": [{"id": s.id, "name": s.name} for s in rows]}
""",
    "app/blueprints/inventory/routes.py": """\
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ...extensions import db
from ...models.catalog import Product

bp = Blueprint("inventory", __name__)


@bp.post("/products")
@jwt_required()
def create_product():
    ident = get_jwt_identity() or {}
    org_id = ident.get("org_id")
    data = request.get_json() or {}
    p = Product(
        org_id=org_id,
        sku=data.get("sku"),
        name=data.get("name"),
        unit=data.get("unit", "pcs"),
        price=data.get("price", 0),
        tax_rate=data.get("tax_rate", 0),
        opening_stock=data.get("opening_stock", 0),
    )
    db.session.add(p)
    db.session.commit()
    return {"id": p.id, "name": p.name}, 201


@bp.get("/products")
@jwt_required()
def list_products():
    ident = get_jwt_identity() or {}
    org_id = ident.get("org_id")
    rows = db.session.scalars(db.select(Product).filter_by(org_id=org_id)).all()
    return {
        "products": [
            {
                "id": r.id,
                "sku": r.sku,
                "name": r.name,
                "unit": r.unit,
                "price": float(r.price or 0),
                "tax_rate": float(r.tax_rate or 0),
                "opening_stock": float(r.opening_stock or 0),
            }
            for r in rows
        ]
    }
""",
    "app/blueprints/sales/routes.py": """\
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from decimal import Decimal
from ...extensions import db
from ...models.sales import Invoice, InvoiceItem, Customer, Payment

bp = Blueprint("sales", __name__)


def _d(v):
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal(0)


@bp.post("/customers")
@jwt_required()
def create_customer():
    ident = get_jwt_identity() or {}
    org_id = ident.get("org_id")
    data = request.get_json() or {}
    c = Customer(org_id=org_id, name=data.get("name"), phone=data.get("phone"), gstin=data.get("gstin"))
    db.session.add(c)
    db.session.commit()
    return {"id": c.id, "name": c.name}, 201


@bp.post("/invoice")
@jwt_required()
def create_invoice():
    ident = get_jwt_identity() or {}
    org_id = ident.get("org_id")
    data = request.get_json() or {}

    items = data.get("items", [])
    subtotal = Decimal(0)
    taxtotal = Decimal(0)
    for it in items:
        qty = _d(it.get("qty", 1))
        rate = _d(it.get("rate", 0))
        tax_rate = _d(it.get("tax_rate", 0))
        line_no_tax = qty * rate
        tax_val = (line_no_tax * tax_rate) / Decimal(100)
        subtotal += line_no_tax
        taxtotal += tax_val

    inv = Invoice(
        org_id=org_id,
        store_id=data.get("store_id"),
        customer_id=data.get("customer_id"),
        number=data.get("number"),
        subtotal=subtotal,
        tax_total=taxtotal,
        total=subtotal + taxtotal,
        status="due",
    )
    db.session.add(inv)
    db.session.flush()

    for it in items:
        qty = _d(it.get("qty", 1))
        rate = _d(it.get("rate", 0))
        tax_rate = _d(it.get("tax_rate", 0))
        line_total = (qty * rate) * (Decimal(1) + tax_rate / Decimal(100))
        db.session.add(
            InvoiceItem(
                invoice_id=inv.id,
                product_id=it.get("product_id"),
                description=it.get("description"),
                qty=qty,
                rate=rate,
                tax_rate=tax_rate,
                line_total=line_total,
            )
        )

    db.session.commit()
    return {"id": inv.id, "number": inv.number, "total": float(inv.total)}, 201


@bp.get("/invoices")
@jwt_required()
def list_invoices():
    ident = get_jwt_identity() or {}
    org_id = ident.get("org_id")
    rows = db.session.scalars(db.select(Invoice).filter_by(org_id=org_id)).all()
    return {
        "invoices": [
            {"id": r.id, "number": r.number, "total": float(r.total or 0), "status": r.status} for r in rows
        ]
    }


@bp.post("/invoices/mark-paid")
@jwt_required()
def mark_paid():
    inv_id = int((request.args.get("id") or request.get_json().get("id") or 0))
    inv = db.session.get(Invoice, inv_id)
    if not inv:
        return {"error": "invoice not found"}, 404
    inv.status = "paid"
    db.session.commit()
    return {"ok": True}


@bp.post("/payment-record")
@jwt_required()
def record_payment():
    ident = get_jwt_identity() or {}
    org_id = ident.get("org_id")
    data = request.get_json() or {}
    pay = Payment(
        invoice_id=data.get("invoice_id"),
        org_id=org_id,
        method=data.get("method", "UPI"),
        amount=_d(data.get("amount", 0)),
        ref=data.get("ref"),
    )
    db.session.add(pay)
    inv = db.session.get(Invoice, data.get("invoice_id"))
    if inv:
        inv.status = "paid"
    db.session.commit()
    return {"id": pay.id}
""",
    "app/blueprints/payments/routes.py": """\
from flask import Blueprint, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from decimal import Decimal
from ...extensions import db
from ...models.sales import Invoice, Payment
from ...services.upi import get_upi_provider
from ...utils.feature_flags import is_enabled

bp = Blueprint("payments", __name__)


@bp.post("/collect")
@jwt_required()
def create_collect():
    if not is_enabled("UPI"):
        return {"error": "UPI disabled"}, 400
    ident = get_jwt_identity() or {}
    org_id = ident.get("org_id")
    data = request.get_json() or {}
    invoice_id = data.get("invoice_id")
    payee_vpa = data.get("payee_vpa", "merchant@upi")
    inv = db.session.get(Invoice, invoice_id)
    if not inv or inv.org_id != org_id:
        return {"error": "invoice not found"}, 404
    provider = get_upi_provider(current_app.config.get("PSP_PROVIDER"))
    payload = provider.create_collect_request(
        payee_vpa=payee_vpa,
        amount=float(inv.total or Decimal(0)),
        txn_note=f"Invoice {inv.number}",
        invoice_number=inv.number or str(inv.id),
    )
    return {"invoice_id": inv.id, **payload}


@bp.post("/webhook/mock-paid")
def webhook_mock_paid():
    data = request.get_json() or {}
    invoice_id = data.get("invoice_id")
    ref = data.get("ref", "MOCKREF")
    amount = Decimal(str(data.get("amount", 0)))
    inv = db.session.get(Invoice, invoice_id)
    if not inv:
        return {"error": "invoice not found"}, 404
    inv.status = "paid"
    pay = Payment(invoice_id=inv.id, org_id=inv.org_id, amount=amount, ref=ref, method="UPI")
    db.session.add(pay)
    db.session.commit()
    return {"ok": True}
""",
    "app/blueprints/expenses/routes.py": """\
from flask import Blueprint

bp = Blueprint("expenses", __name__)


@bp.get("/")
def expenses_ping():
    return {"ready": True}
""",
    "app/blueprints/reports/routes.py": """\
from flask import Blueprint

bp = Blueprint("reports", __name__)


@bp.get("/ping")
def ping():
    return {"ok": True}
""",
}


def write(path: str, content: str) -> None:
    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as fh:
        fh.write(textwrap.dedent(content))


def main() -> None:
    pathlib.Path("instance").mkdir(exist_ok=True)
    for path, content in FILES.items():
        write(path, content)
    print("[ok] SuperApp v2 scaffold created.")
    print("Next:")
    print("  python -m venv .venv && .venv/Scripts/activate  (on Windows)")
    print("  pip install -r requirements.txt")
    print("  cp .env.example .env")
    print("  python manage.py")
    print("Health: GET http://127.0.0.1:5000/health")


if __name__ == "__main__":
    main()
