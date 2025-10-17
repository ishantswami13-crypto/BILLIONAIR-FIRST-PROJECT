from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import func

from ..extensions import db
from ..models import Customer, Sale
from ..utils.decorators import login_required

customers_bp = Blueprint('customers', __name__)


@customers_bp.route('/customers')
@login_required
def customers():
    rows = (
        db.session.query(
            Customer.id,
            Customer.name,
            Customer.phone,
            func.coalesce(func.count(Sale.id), 0),
            func.coalesce(func.sum(Sale.net_total), 0),
            func.max(Sale.date),
        )
        .outerjoin(Sale, Sale.customer_id == Customer.id)
        .group_by(Customer.id)
        .order_by(func.coalesce(func.sum(Sale.net_total), 0).desc())
        .all()
    )

    customers_data = []
    for cid, name, phone, orders, total, last_date in rows:
        last_purchase = last_date.strftime('%Y-%m-%d') if last_date else None
        customers_data.append(
            (
                cid,
                name,
                phone or 'N/A',
                int(orders or 0),
                float(total or 0),
                last_purchase,
            )
        )

    return render_template('customers/list.html', customers=customers_data)


@customers_bp.route('/customers/new', methods=['GET', 'POST'])
@login_required
def customers_new():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        phone = (request.form.get('phone') or '').strip() or None
        if not name:
            flash('Name is required.', 'warning')
            return redirect(url_for('customers.customers_new'))

        existing = Customer.query.filter(func.lower(Customer.name) == name.lower()).first()
        if existing:
            if phone and not existing.phone:
                existing.phone = phone
        else:
            db.session.add(Customer(name=name, phone=phone))

        db.session.commit()
        flash('Customer saved.', 'success')
        return redirect(url_for('customers.customers'))

    return render_template('customers/new.html')
