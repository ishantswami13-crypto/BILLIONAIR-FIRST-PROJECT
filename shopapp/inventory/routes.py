from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Item
from ..utils.decorators import login_required

inventory_bp = Blueprint('inventory', __name__)


@inventory_bp.route('/items', methods=['GET', 'POST'])
@login_required
def items():
    if request.method == 'POST':
        name = request.form['name'].strip()
        price = float(request.form['price'])
        stock = int(request.form.get('stock', 0) or 0)
        try:
            db.session.add(Item(name=name, price=price, current_stock=stock))
            db.session.commit()
            flash('Item added.')
        except IntegrityError:
            db.session.rollback()
            flash('Item already exists.')
        return redirect(url_for('inventory.items'))

    rows = Item.query.order_by(Item.name).all()
    return render_template('inventory/items.html', items=rows)
