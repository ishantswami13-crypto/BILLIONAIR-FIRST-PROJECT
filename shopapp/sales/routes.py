from datetime import datetime, timedelta

from flask import (Blueprint, redirect, render_template, request, send_file,
                   session, url_for)
from sqlalchemy import func

from ..extensions import db
from ..models import AuditLog, Credit, Customer, Expense, Item, Sale
from ..utils.decorators import login_required
from ..utils.mailer import send_mail
from ..utils.pdfs import create_invoice_pdf

sales_bp = Blueprint('sales', __name__)


def today_bounds() -> tuple[datetime, datetime]:
    now = datetime.utcnow()
    start = datetime(now.year, now.month, now.day)
    end = start + timedelta(days=1) - timedelta(seconds=1)
    return start, end


@sales_bp.route('/')
@login_required
def index():
    start, end = today_bounds()

    items = Item.query.order_by(Item.name).all()
    sales = Sale.query.order_by(Sale.date.desc()).limit(20).all()
    customers = Customer.query.order_by(Customer.name).all()

    row = (db.session.query(
        func.coalesce(func.sum(Sale.net_total), 0),
        func.coalesce(func.sum(Sale.discount), 0),
        func.coalesce(func.sum(Sale.tax), 0),
        func.count(Sale.id)
    ).filter(Sale.date.between(start, end)).first())

    today_rev = float(row[0] or 0)
    today_discount = float(row[1] or 0)
    today_tax = float(row[2] or 0)
    today_count = int(row[3] or 0)

    payment_summary = (
        db.session.query(Sale.payment_method,
                         func.coalesce(func.sum(Sale.net_total), 0))
        .filter(Sale.date.between(start, end))
        .group_by(Sale.payment_method)
        .all()
    )
    payment_summary = [
        {'method': method or 'cash', 'amount': float(amount or 0)}
        for method, amount in payment_summary
    ]

    low_stock = (
        Item.query
        .filter(Item.current_stock <= func.coalesce(Item.reorder_level, 5))
        .order_by(Item.current_stock.asc(), Item.name)
        .limit(8)
        .all()
    )

    outstanding_udhar = (
        db.session.query(func.coalesce(func.sum(Credit.total), 0))
        .filter(Credit.status.in_(['unpaid', 'adjusted']))
        .scalar() or 0
    )

    start_window = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)
    window_days = [start_window.date() + timedelta(days=i) for i in range(7)]

    sales_rows = (
        db.session.query(func.date(Sale.date), func.coalesce(func.sum(Sale.net_total), 0))
        .filter(Sale.date >= start_window)
        .group_by(func.date(Sale.date))
        .all()
    )
    expenses_rows = (
        db.session.query(Expense.date, func.coalesce(func.sum(Expense.amount), 0))
        .filter(Expense.date >= window_days[0])
        .group_by(Expense.date)
        .all()
    )

    sales_map = {row[0]: float(row[1] or 0) for row in sales_rows}
    expenses_map = {row[0]: float(row[1] or 0) for row in expenses_rows}

    chart_labels = [day.strftime('%d %b') for day in window_days]
    chart_sales = [round(sales_map.get(day, 0.0), 2) for day in window_days]
    chart_expenses = [round(expenses_map.get(day, 0.0), 2) for day in window_days]
    chart_profit = [round(s - e, 2) for s, e in zip(chart_sales, chart_expenses)]

    payment_chart = {
        'labels': [row['method'].title() for row in payment_summary],
        'amounts': [row['amount'] for row in payment_summary]
    }

    invoice_ready = session.pop('invoice_ready', None)

    return render_template(
        'index.html',
        user=session.get('user'),
        items=items,
        sales=sales,
        customers=customers,
        today_rev=today_rev,
        today_discount=today_discount,
        today_tax=today_tax,
        today_count=today_count,
        payment_summary=payment_summary,
        low_stock=low_stock,
        outstanding_udhar=outstanding_udhar,
        invoice_ready=invoice_ready,
        chart_labels=chart_labels,
        chart_sales=chart_sales,
        chart_expenses=chart_expenses,
        chart_profit=chart_profit,
        payment_chart=payment_chart
    )


@sales_bp.route('/sell', methods=['POST'])
@login_required
def sell():
    item_id = int(request.form['item_id'])
    quantity = int(request.form['quantity'])
    customer_id_raw = request.form.get('customer_id')
    customer_id = int(customer_id_raw) if customer_id_raw else None
    customer_name = request.form.get('customer_name', '').strip()
    sale_type = (request.form.get('sale_type') or 'paid').lower()
    payment_method = (request.form.get('payment_method') or 'cash').lower()
    if sale_type == 'udhar':
        payment_method = 'udhar'
    discount = float(request.form.get('discount') or 0)
    voice_transcript = (request.form.get('voice_transcript') or '').strip()

    item = Item.query.get(item_id)
    if not item:
        return 'Item not found', 404
    if quantity > item.current_stock:
        return 'Not enough stock', 400

    customer = None
    if customer_id:
        customer = Customer.query.get(customer_id)
    elif customer_name:
        customer = Customer.query.filter_by(name=customer_name).first()
        if not customer:
            customer = Customer(name=customer_name)
            db.session.add(customer)
            db.session.flush()

    subtotal = item.price * quantity
    gst_rate = item.gst_rate or 0
    taxable = max(subtotal - discount, 0)
    tax = round(taxable * (gst_rate / 100), 2)
    net_total = round(taxable + tax, 2)

    item.current_stock -= quantity

    sale = Sale(
        item=item.name,
        quantity=quantity,
        total=net_total,
        customer_id=customer.id if customer else customer_id,
        payment_method=payment_method,
        discount=discount,
        tax=tax,
        net_total=net_total
    )
    db.session.add(sale)

    if sale_type == 'udhar':
        credit_name = customer.name if customer else customer_name
        if not credit_name:
            return 'Customer required for udhar', 400
        db.session.add(Credit(
            customer_name=credit_name,
            item=item.name,
            quantity=quantity,
            total=net_total,
            status='unpaid'
        ))

    audit_details = {'item': item.name, 'quantity': quantity}
    if voice_transcript:
        audit_details['voice_transcript'] = voice_transcript

    db.session.add(AuditLog(
        user=session.get('user'),
        action='sell',
        details=str(audit_details)
    ))

    db.session.commit()

    invoice_path = create_invoice_pdf(sale.id)
    if invoice_path:
        session['invoice_ready'] = sale.id

    return redirect(url_for('sales.index'))


@sales_bp.route('/invoice/<int:sale_id>')
@login_required
def invoice(sale_id: int):
    path = create_invoice_pdf(sale_id)
    if not path:
        return 'Sale not found', 404
    return send_file(
        path,
        as_attachment=True,
        download_name=f'invoice_{sale_id}.pdf',
        mimetype='application/pdf'
    )


@sales_bp.route('/send_invoice/<int:sale_id>')
@login_required
def send_invoice_route(sale_id: int):
    sale = Sale.query.get(sale_id)
    if not sale or not sale.customer_id:
        return 'No customer linked to sale.', 400

    customer = Customer.query.get(sale.customer_id)
    if not customer or not customer.email:
        return 'Customer email not found.', 400

    create_invoice_pdf(sale_id)
    body = (
        f'Dear {customer.name},\n\n'
        f'Your invoice for sale #{sale_id} is ready.\n'
        'You can download it from your account.\n\n'
        'Thank you for shopping with us.'
    )
    send_mail(customer.email, f'Invoice #{sale_id:05d}', body)

    db.session.add(AuditLog(
        user=session.get('user'),
        action='send_invoice_email',
        details=str({'sale_id': sale_id, 'to': customer.email})
    ))
    db.session.commit()

    return redirect(url_for('sales.index'))
