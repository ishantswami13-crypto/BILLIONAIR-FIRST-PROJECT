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
