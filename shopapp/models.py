from datetime import datetime, date

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='admin')
    email = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    email_verified = db.Column(db.Boolean, default=False)

    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)


class Setting(db.Model):
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    value = db.Column(db.String(255))


class ShopProfile(db.Model):
    __tablename__ = 'shop_profile'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    address = db.Column(db.Text)
    phone = db.Column(db.String(50))
    gst = db.Column(db.String(50))
    logo_path = db.Column(db.String(255))
    invoice_prefix = db.Column(db.String(20), default='INV')
    primary_color = db.Column(db.String(20))
    secondary_color = db.Column(db.String(20))
    signature_path = db.Column(db.String(255))
    watermark_path = db.Column(db.String(255))


class Item(db.Model):
    __tablename__ = 'items'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    price = db.Column(db.Float, nullable=False)
    current_stock = db.Column(db.Integer, default=0)
    barcode = db.Column(db.String(255))
    gst_rate = db.Column(db.Float, default=0)
    reorder_level = db.Column(db.Integer, default=5)
    hsn = db.Column(db.String(50))


class Customer(db.Model):
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(255))
    address = db.Column(db.Text)
    gstin = db.Column(db.String(50))

    sales = db.relationship('Sale', backref='customer', lazy=True)


class Sale(db.Model):
    __tablename__ = 'sales'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    item = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Float, default=0)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    payment_method = db.Column(db.String(50), default='cash')
    discount = db.Column(db.Float, default=0)
    tax = db.Column(db.Float, default=0)
    net_total = db.Column(db.Float, default=0)
    invoice_number = db.Column(db.String(64), unique=True)
    locked = db.Column(db.Boolean, default=False, nullable=False)


class Credit(db.Model):
    __tablename__ = 'credits'

    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(255))
    item = db.Column(db.String(255))
    quantity = db.Column(db.Integer)
    total = db.Column(db.Float)
    status = db.Column(db.String(20), default='unpaid')
    date = db.Column(db.DateTime, default=datetime.utcnow)


class Supplier(db.Model):
    __tablename__ = 'suppliers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    contact_name = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(255))
    address = db.Column(db.Text)
    notes = db.Column(db.Text)


class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    order_date = db.Column(db.Date, default=date.today)
    status = db.Column(db.String(50), default='received')
    total_cost = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)


class PurchaseItem(db.Model):
    __tablename__ = 'purchase_items'

    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'))
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    quantity = db.Column(db.Integer)
    cost_price = db.Column(db.Float)


class ExpenseCategory(db.Model):
    __tablename__ = 'expense_categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    color = db.Column(db.String(20), default='#62b5ff')
    keywords = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Expense(db.Model):
    __tablename__ = 'expenses'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=date.today)
    category = db.Column(db.String(255))
    category_id = db.Column(db.Integer, db.ForeignKey('expense_categories.id'))
    amount = db.Column(db.Float)
    notes = db.Column(db.Text)

    category_rel = db.relationship('ExpenseCategory', backref='expenses', lazy=True)


class AuditLog(db.Model):
    __tablename__ = 'audit_log'

    id = db.Column(db.Integer, primary_key=True)
    ts = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.Column(db.String(80))
    action = db.Column(db.String(120))
    details = db.Column(db.Text)
    resource_type = db.Column(db.String(64))
    resource_id = db.Column(db.Integer)
    before_state = db.Column(db.Text)
    after_state = db.Column(db.Text)
    ip_address = db.Column(db.String(64))
    user_agent = db.Column(db.String(255))


class Return(db.Model):
    __tablename__ = 'returns'

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'))
    item = db.Column(db.String(255))
    quantity = db.Column(db.Integer)
    amount = db.Column(db.Float)
    reason = db.Column(db.String(255))
    date = db.Column(db.DateTime, default=datetime.utcnow)


class Otp(db.Model):
    __tablename__ = 'otps'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80))
    email = db.Column(db.String(255))
    otp = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
