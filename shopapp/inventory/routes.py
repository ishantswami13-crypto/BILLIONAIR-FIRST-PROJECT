from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Item, PurchaseItem, PurchaseOrder, Supplier
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
            flash('Item added.', 'success')
        except IntegrityError:
            db.session.rollback()
            flash('Item already exists.', 'warning')
        return redirect(url_for('inventory.items'))

    rows = Item.query.order_by(Item.name).all()
    return render_template('inventory/items.html', items=rows)

@inventory_bp.route('/inventory/add_stock', methods=['POST'])
@login_required
def add_stock():
    item_id_raw = request.form.get('item_id')
    quantity_raw = request.form.get('quantity')

    if not item_id_raw:
        flash('Select an item to update.', 'warning')
        return redirect(url_for('inventory.items'))

    try:
        item_id = int(item_id_raw)
    except (TypeError, ValueError):
        flash('Select a valid item.', 'warning')
        return redirect(url_for('inventory.items'))

    try:
        quantity = int(quantity_raw or '')
    except (TypeError, ValueError):
        flash('Provide a valid quantity.', 'warning')
        return redirect(url_for('inventory.items'))

    if quantity <= 0:
        flash('Quantity must be greater than zero.', 'warning')
        return redirect(url_for('inventory.items'))

    item = Item.query.get(item_id)
    if not item:
        flash('Item not found.', 'warning')
        return redirect(url_for('inventory.items'))

    item.current_stock = (item.current_stock or 0) + quantity
    item.updated_at = datetime.utcnow()
    db.session.add(item)
    db.session.commit()
    flash(f'Added {quantity} units to {item.name}.', 'success')
    return redirect(url_for('inventory.items'))


@inventory_bp.route('/inventory/reorder', methods=['GET', 'POST'])
@login_required
def reorder():
    items = Item.query.order_by(Item.reorder_level.asc(), Item.name.asc()).all()
    low_stock: list[dict[str, float | int | str]] = []
    for item in items:
        reorder_level = item.reorder_level or 5
        current_stock = item.current_stock or 0
        if current_stock <= reorder_level:
            recommended = max(reorder_level * 2 - current_stock, reorder_level)
            low_stock.append(
                {
                    "id": item.id,
                    "name": item.name,
                    "current_stock": current_stock,
                    "reorder_level": reorder_level,
                    "recommended": recommended,
                    "price": float(item.price or 0),
                }
            )

    suppliers = Supplier.query.order_by(Supplier.name.asc()).all()

    if request.method == 'POST':
        if not suppliers:
            flash('Add a supplier before generating purchase orders.', 'warning')
            return redirect(url_for('inventory.reorder'))

        supplier_id_raw = request.form.get('supplier_id')
        try:
            supplier_id = int(supplier_id_raw)
        except (TypeError, ValueError):
            flash('Select a supplier to continue.', 'warning')
            return redirect(url_for('inventory.reorder'))

        supplier = Supplier.query.get(supplier_id)
        if not supplier:
            flash('Supplier not found.', 'warning')
            return redirect(url_for('inventory.reorder'))

        order = PurchaseOrder(
            supplier_id=supplier.id,
            status='draft',
            notes=request.form.get('notes') or '',
        )
        db.session.add(order)
        db.session.flush()

        total_cost = 0.0
        line_count = 0

        for item in items:
            qty_raw = request.form.get(f'qty_{item.id}')
            if not qty_raw:
                continue
            try:
                qty = int(qty_raw)
            except (TypeError, ValueError):
                qty = 0
            if qty <= 0:
                continue

            purchase_item = PurchaseItem(
                purchase_id=order.id,
                item_id=item.id,
                quantity=qty,
                cost_price=float(item.price or 0),
            )
            db.session.add(purchase_item)
            total_cost += qty * float(item.price or 0)
            line_count += 1

        if line_count == 0:
            db.session.rollback()
            flash('Select at least one item with quantity greater than zero.', 'warning')
            return redirect(url_for('inventory.reorder'))

        order.total_cost = total_cost
        db.session.add(order)
        db.session.commit()
        flash(f'Draft purchase order #{order.id} created with {line_count} lines.', 'success')
        return redirect(url_for('inventory.reorder'))

    recommended_total = sum(entry["recommended"] * entry["price"] for entry in low_stock)
    return render_template(
        'inventory/reorder.html',
        low_stock=low_stock,
        suppliers=suppliers,
        recommended_total=recommended_total,
        inventory_items=items,
    )


@inventory_bp.route('/inventory/suppliers', methods=['GET', 'POST'])
@login_required
def suppliers():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        contact_name = (request.form.get('contact_name') or '').strip()
        phone = (request.form.get('phone') or '').strip()
        email = (request.form.get('email') or '').strip()
        address = (request.form.get('address') or '').strip()
        notes = (request.form.get('notes') or '').strip()

        if not name:
            flash('Supplier name is required.', 'warning')
            return redirect(url_for('inventory.suppliers'))

        supplier = Supplier(
            name=name,
            contact_name=contact_name or None,
            phone=phone or None,
            email=email or None,
            address=address or None,
            notes=notes or None,
        )
        try:
            db.session.add(supplier)
            db.session.commit()
            flash('Supplier added.', 'success')
        except IntegrityError:
            db.session.rollback()
            flash('Supplier with that name already exists.', 'warning')
        return redirect(url_for('inventory.suppliers'))

    rows = Supplier.query.order_by(Supplier.name.asc()).all()
    return render_template('inventory/suppliers.html', suppliers=rows)


@inventory_bp.route('/inventory/orders', methods=['GET', 'POST'])
@login_required
def orders():
    if request.method == 'POST':
        action = request.form.get('action', '').strip().lower()
        order_id_raw = request.form.get('order_id')
        try:
            order_id = int(order_id_raw)
        except (TypeError, ValueError):
            flash('Invalid purchase order reference.', 'warning')
            return redirect(url_for('inventory.orders'))

        order = PurchaseOrder.query.get(order_id)
        if not order:
            flash('Purchase order not found.', 'warning')
            return redirect(url_for('inventory.orders'))

        if action == 'issue':
            if order.status != 'draft':
                flash('Purchase order already issued.', 'info')
                return redirect(url_for('inventory.orders'))
            order.status = 'issued'
            order.order_date = datetime.utcnow().date()
            db.session.add(order)
            db.session.commit()
            flash(f'Purchase order #{order.id} marked as issued.', 'success')
        elif action == 'receive':
            if order.status == 'received':
                flash('Purchase order already received.', 'info')
                return redirect(url_for('inventory.orders'))
            for line in order.lines:
                if line.item and line.quantity:
                    line.item.current_stock = (line.item.current_stock or 0) + line.quantity
                    db.session.add(line.item)
            order.status = 'received'
            order.received_at = datetime.utcnow()
            db.session.add(order)
            db.session.commit()
            flash(f'Purchase order #{order.id} marked as received.', 'success')
        else:
            flash('Unsupported action.', 'warning')
        return redirect(url_for('inventory.orders'))

    orders = (
        PurchaseOrder.query.order_by(PurchaseOrder.created_at.desc())
        .all()
    )
    return render_template('inventory/orders.html', orders=orders)
