from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Customer
from ..utils.decorators import login_required

customers_bp = Blueprint('customers', __name__)


@customers_bp.route('/customers', methods=['GET', 'POST'])
@login_required
def customers():
    if request.method == 'POST':
        name = request.form['name'].strip()
        phone = request.form.get('phone', '').strip() or None
        email = request.form.get('email', '').strip() or None
        address = request.form.get('address', '').strip() or None
        if name:
            existing = Customer.query.filter_by(name=name).first()
            if existing:
                existing.phone = phone or existing.phone
                existing.email = email or existing.email
                existing.address = address or existing.address
            else:
                db.session.add(Customer(name=name, phone=phone, email=email, address=address))
            db.session.commit()
            flash('Customer saved.')
        return redirect(url_for('customers.customers'))

    rows = Customer.query.order_by(Customer.name).all()
    return render_template('customers/list.html', customers=rows)
