from datetime import datetime, date
from decimal import Decimal
import enum

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


class UserRole(enum.Enum):
    owner = "owner"
    cashier = "cashier"
    accountant = "accountant"


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole, name="user_role", native_enum=False), default=UserRole.owner, nullable=False)
    email = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    email_verified = db.Column(db.Boolean, default=False)
    last_login_at = db.Column(db.DateTime)
    last_active_at = db.Column(db.DateTime)
    streak_count = db.Column(db.Integer, default=0)
    xp = db.Column(db.Integer, default=0)
    engagement_opt_out = db.Column(db.Boolean, default=False)

    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    @property
    def normalized_role(self) -> str:
        value = self.role.value if isinstance(self.role, enum.Enum) else self.role
        return (value or "owner").lower()


class UserSession(db.Model):
    __tablename__ = 'user_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_token = db.Column(db.String(64), unique=True, nullable=False)
    user_agent = db.Column(db.String(255))
    ip_address = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = db.Column(db.DateTime)

    user = db.relationship('User', backref=db.backref('sessions', lazy=True))


class Quest(db.Model):
    __tablename__ = 'quests'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    xp_reward = db.Column(db.Integer, nullable=False, default=10)
    is_recurring = db.Column(db.Boolean, nullable=False, default=False)
    daily_limit = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class UserQuest(db.Model):
    __tablename__ = 'user_quests'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    quest_id = db.Column(db.Integer, db.ForeignKey('quests.id'), nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('completed_quests', lazy=True))
    quest = db.relationship('Quest', backref=db.backref('completions', lazy=True))


class Referral(db.Model):
    __tablename__ = 'referrals'

    id = db.Column(db.Integer, primary_key=True)
    inviter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    invitee_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    code = db.Column(db.String(64), unique=True, nullable=False)
    status = db.Column(db.String(20), default='CREATED', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    inviter = db.relationship('User', foreign_keys=[inviter_id], backref=db.backref('referrals', lazy=True))
    invitee = db.relationship('User', foreign_keys=[invitee_id])


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    channel = db.Column(db.String(32), nullable=False)
    template = db.Column(db.String(120), nullable=False)
    payload = db.Column(db.Text)
    sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('notifications', lazy=True))


class FeatureFlag(db.Model):
    __tablename__ = 'feature_flags'

    key = db.Column(db.String(120), primary_key=True)
    enabled = db.Column(db.Boolean, nullable=False, default=False)


class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.String(120), nullable=False)
    props = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('events', lazy=True))


class Setting(db.Model):
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    value = db.Column(db.String(255))


class ShopProfile(db.Model):
    __tablename__ = 'shop_profile'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    shop_name = db.Column(db.String(255))
    currency = db.Column(db.String(8), default='INR')
    timezone = db.Column(db.String(64), default='Asia/Kolkata')
    gst_enabled = db.Column(db.Boolean, default=False)
    low_stock_threshold = db.Column(db.Integer, default=5)
    opening_cash = db.Column(db.Float, default=0)
    address = db.Column(db.Text)
    phone = db.Column(db.String(50))
    gst = db.Column(db.String(50))
    logo_path = db.Column(db.String(255))
    invoice_prefix = db.Column(db.String(20), default='INV')
    primary_color = db.Column(db.String(20))
    secondary_color = db.Column(db.String(20))
    signature_path = db.Column(db.String(255))
    watermark_path = db.Column(db.String(255))
    plan_slug = db.Column(db.String(50), db.ForeignKey('plans.slug'), default='pro')
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'))
    trial_plan_slug = db.Column(db.String(50))
    trial_started_at = db.Column(db.DateTime)
    trial_ends_at = db.Column(db.DateTime)
    trial_cancelled_at = db.Column(db.DateTime)

    plan = db.relationship('Plan', lazy=True, foreign_keys=[plan_id])
    plan_by_slug = db.relationship(
        'Plan',
        lazy=True,
        foreign_keys=[plan_slug],
        primaryjoin='Plan.slug==ShopProfile.plan_slug',
        viewonly=True,
    )

    def active_plan_slug(self) -> str:
        if self.trial_plan_slug and self.trial_ends_at:
            now = datetime.utcnow()
            if self.trial_ends_at >= now:
                return self.trial_plan_slug
        if self.plan_slug:
            return self.plan_slug
        if self.plan and self.plan.slug:
            return self.plan.slug
        if self.plan_by_slug and self.plan_by_slug.slug:
            return self.plan_by_slug.slug
        return 'pro'

    @property
    def trial_active(self) -> bool:
        return bool(
            self.trial_plan_slug and
            self.trial_ends_at and
            self.trial_started_at and
            self.trial_ends_at >= datetime.utcnow()
        )

    @property
    def trial_days_remaining(self) -> int | None:
        if not self.trial_active:
            return None
        delta = self.trial_ends_at - datetime.utcnow()
        return max(0, int(delta.total_seconds() // 86400) + (1 if delta.total_seconds() % 86400 else 0))

    @property
    def default_location(self):
        return next((location for location in getattr(self, "locations", []) if location.is_default), None)


class ShopLocation(db.Model):
    __tablename__ = 'shop_locations'

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('shop_profile.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    gstin = db.Column(db.String(20))
    state_code = db.Column(db.String(4))
    address = db.Column(db.Text)
    city = db.Column(db.String(120))
    pincode = db.Column(db.String(10))
    phone = db.Column(db.String(20))
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = db.relationship(
        'ShopProfile',
        backref=db.backref('locations', lazy=True, cascade='all, delete-orphan'),
    )


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Customer(db.Model):
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(255))
    address = db.Column(db.Text)
    gstin = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sales = db.relationship('Sale', back_populates='customer', lazy=True)


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
    location_id = db.Column(db.Integer, db.ForeignKey('shop_locations.id'))
    gst_status = db.Column(db.String(20), default='pending', nullable=False)
    irn = db.Column(db.String(64))
    ack_no = db.Column(db.String(64))
    ack_date = db.Column(db.DateTime)
    signed_invoice_path = db.Column(db.String(255))
    eway_bill_no = db.Column(db.String(64))
    eway_valid_upto = db.Column(db.DateTime)

    customer = db.relationship('Customer', back_populates='sales', lazy=True)
    location = db.relationship('ShopLocation', backref=db.backref('sales', lazy=True))
    payment_intents = db.relationship('PaymentIntent', backref='sale', lazy=True)


class EInvoiceSubmission(db.Model):
    __tablename__ = 'einvoice_submissions'

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)
    payload = db.Column(db.Text)
    response = db.Column(db.Text)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    submitted_at = db.Column(db.DateTime)
    acknowledged_at = db.Column(db.DateTime)

    sale = db.relationship('Sale', backref=db.backref('einvoice_submissions', lazy=True))


class PaymentIntent(db.Model):
    __tablename__ = 'payment_intents'

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'))
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(8), default='INR', nullable=False)
    provider = db.Column(db.String(32), nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)
    customer_reference = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    meta_info = db.Column('metadata', db.Text)

    transactions = db.relationship('PaymentTransaction', backref='intent', lazy=True, cascade='all, delete-orphan')


class PaymentTransaction(db.Model):
    __tablename__ = 'payment_transactions'

    id = db.Column(db.Integer, primary_key=True)
    intent_id = db.Column(db.Integer, db.ForeignKey('payment_intents.id'), nullable=False)
    provider = db.Column(db.String(32), nullable=False)
    status = db.Column(db.String(20), default='created', nullable=False)
    amount = db.Column(db.Float, nullable=False)
    reference = db.Column(db.String(120))
    raw_response = db.Column(db.Text)
    error = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    processed_at = db.Column(db.DateTime)


class Credit(db.Model):
    __tablename__ = 'credits'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    customer_name = db.Column(db.String(255))
    item = db.Column(db.String(255))
    quantity = db.Column(db.Integer)
    total = db.Column(db.Float)
    status = db.Column(db.String(20), default='unpaid')
    date = db.Column(db.DateTime, default=datetime.utcnow)
    last_reminder_at = db.Column(db.DateTime)
    reminder_count = db.Column(db.Integer, default=0)
    reminder_opt_out = db.Column(db.Boolean, default=False, nullable=False)
    reminder_phone = db.Column(db.String(50))

    customer = db.relationship('Customer', lazy=True)


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
    status = db.Column(db.String(50), default='draft')
    total_cost = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    received_at = db.Column(db.DateTime)

    supplier = db.relationship('Supplier', backref=db.backref('orders', lazy=True))


class PurchaseItem(db.Model):
    __tablename__ = 'purchase_items'

    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'))
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    quantity = db.Column(db.Integer)
    cost_price = db.Column(db.Float)

    order = db.relationship('PurchaseOrder', backref=db.backref('lines', lazy=True, cascade='all, delete-orphan'))
    item = db.relationship('Item', lazy=True)


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


class AssistantSession(db.Model):
    __tablename__ = 'assistant_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AssistantMessage(db.Model):
    __tablename__ = 'assistant_messages'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('assistant_sessions.id'), nullable=False)
    role = db.Column(db.String(20))
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    session = db.relationship('AssistantSession', backref='messages', lazy=True)


class UserInvite(db.Model):
    __tablename__ = 'user_invites'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole, name="invite_role", native_enum=False), nullable=False, default=UserRole.cashier)
    token = db.Column(db.String(64), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    accepted_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    invited_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.String(20), default='pending', nullable=False)
    last_sent_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    invited_by = db.relationship('User', backref=db.backref('sent_invites', lazy=True))


class ApiWebhook(db.Model):
    __tablename__ = 'api_webhooks'

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(80), nullable=False)
    event = db.Column(db.String(120), nullable=False)
    target_url = db.Column(db.String(255))
    secret = db.Column(db.String(255))
    status = db.Column(db.String(20), default='active', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_success_at = db.Column(db.DateTime)
    retry_window = db.Column(db.Integer, default=15)  # minutes


class WebhookEvent(db.Model):
    __tablename__ = 'webhook_events'

    id = db.Column(db.Integer, primary_key=True)
    webhook_id = db.Column(db.Integer, db.ForeignKey('api_webhooks.id'), nullable=False)
    external_id = db.Column(db.String(120))
    status = db.Column(db.String(20), default='pending', nullable=False)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    payload = db.Column(db.Text)
    last_error = db.Column(db.Text)
    next_retry_at = db.Column(db.DateTime)
    matched_sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    processed_at = db.Column(db.DateTime)

    webhook = db.relationship('ApiWebhook', backref=db.backref('events', lazy=True, order_by="WebhookEvent.created_at.desc()"))


class Plan(db.Model):
    __tablename__ = 'plans'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    price_monthly = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    currency = db.Column(db.String(8), default='INR')
    description = db.Column(db.Text)
    highlight = db.Column(db.Boolean, default=False, nullable=False)
    display_order = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    trial_days = db.Column(db.Integer, default=0)

    features = db.relationship('PlanFeature', backref='plan', cascade='all, delete-orphan', lazy=True)


class PlanFeature(db.Model):
    __tablename__ = 'plan_features'

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id', ondelete='CASCADE'), nullable=False)
    code = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255))

    __table_args__ = (db.UniqueConstraint('plan_id', 'code', name='uq_plan_feature_code'),)
