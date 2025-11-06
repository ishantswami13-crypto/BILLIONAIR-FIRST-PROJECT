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
