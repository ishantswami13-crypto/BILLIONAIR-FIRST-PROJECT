import csv
import io
from datetime import datetime, timedelta

from flask import (Blueprint, current_app, flash, make_response, redirect, render_template,
                   request, send_file, session, url_for)
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import AuditLog, Credit, Customer, Expense, Item, Sale, Setting
from ..utils.decorators import login_required
from ..utils.audit import log_event
from ..utils.invoices import next_invoice_number
from ..utils.mail import send_mail
from ..utils.pdfs import create_invoice_pdf

sales_bp = Blueprint('sales', __name__)


def today_bounds() -> tuple[datetime, datetime]:
    now = datetime.utcnow()
    start = datetime(now.year, now.month, now.day)
    end = start + timedelta(days=1) - timedelta(seconds=1)
    return start, end


def _parse_range(start_str: str | None, end_str: str | None) -> tuple[str | None, str | None, datetime | None, datetime | None]:
    start_dt = None
    end_dt = None

    if start_str:
        try:
            start_dt = datetime.strptime(start_str, '%Y-%m-%d')
        except ValueError:
            start_str = None
            start_dt = None

    if end_str:
        try:
            end_dt = datetime.strptime(end_str, '%Y-%m-%d') + timedelta(days=1)
        except ValueError:
            end_str = None
            end_dt = None

    return start_str, end_str, start_dt, end_dt


@sales_bp.route('/')
@login_required
def index():
    start, end = today_bounds()

    items = Item.query.order_by(Item.name.asc()).all()
    customers = Customer.query.order_by(Customer.name.asc()).all()

    today_row = (
        db.session.query(
            func.count(Sale.id),
            func.coalesce(func.sum(Sale.net_total), 0),
        )
        .filter(Sale.date.between(start, end))
        .first()
    )

    today_count = int(today_row[0] or 0)
    today_rev = float(today_row[1] or 0.0)

    unpaid_credits = (
        db.session.query(func.coalesce(func.sum(Credit.total), 0))
        .filter(Credit.status == 'unpaid')
        .scalar() or 0.0
    )

    low_stock_count = (
        db.session.query(func.count(Item.id))
        .filter(Item.current_stock <= func.coalesce(Item.reorder_level, 5))
        .scalar() or 0
    )

    window_end = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    window_start = window_end - timedelta(days=6)
    window_days = [window_start.date() + timedelta(days=i) for i in range(7)]

    sales_rows = (
        db.session.query(func.date(Sale.date), func.coalesce(func.sum(Sale.net_total), 0))
        .filter(Sale.date >= window_start)
        .group_by(func.date(Sale.date))
        .all()
    )
    expenses_rows = (
        db.session.query(Expense.date, func.coalesce(func.sum(Expense.amount), 0))
        .filter(Expense.date >= window_days[0])
        .group_by(Expense.date)
        .all()
    )

    def _key(value):
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return value.isoformat()

    sales_map = {_key(day): float(total or 0) for day, total in sales_rows}
    expenses_map = {_key(day): float(total or 0) for day, total in expenses_rows}

    today = datetime.utcnow().date()
    mini = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        iso = day.isoformat()
        mini.append(
            {
                "t": iso[5:],
                "rev": round(sales_map.get(iso, 0.0), 2),
                "exp": round(expenses_map.get(iso, 0.0), 2),
            }
        )

    streak_text = "Keep going!"
    if today_rev > 0:
        streak_text = "You’re on a profit streak 🔥"

    return render_template(
        'index.html',
        items=items,
        customers=customers,
        today_count=today_count,
        today_rev=today_rev,
        unpaid_credits=unpaid_credits,
        low_stock_count=low_stock_count,
        tiny_chart=mini,
        streak_text=streak_text,
        active_plan=current_app.config.get('ACTIVE_PLAN'),
        app_version=current_app.config.get('APP_VERSION'),
        encryption_notice=current_app.config.get('DATA_ENCRYPTION_NOTICE'),
    )


@sales_bp.route('/sales')
@login_required
def history():
    start_str, end_str, start_dt, end_dt = _parse_range(request.args.get('start'), request.args.get('end'))

    query = Sale.query.options(joinedload(Sale.customer))
    if start_dt:
        query = query.filter(Sale.date >= start_dt)
    if end_dt:
        query = query.filter(Sale.date < end_dt)

    sales = query.order_by(Sale.date.desc()).limit(50).all()
    total_amount = sum(float(sale.net_total or 0) for sale in sales)

    return render_template(
        'sales/history.html',
        sales=sales,
        start=start_str,
        end=end_str,
        total_amount=total_amount,
    )


@sales_bp.route('/sales/export.csv')
@login_required
def export_csv():
    start_str, end_str, start_dt, end_dt = _parse_range(request.args.get('start'), request.args.get('end'))

    query = Sale.query.options(joinedload(Sale.customer)).order_by(Sale.date.asc())
    if start_dt:
        query = query.filter(Sale.date >= start_dt)
    if end_dt:
        query = query.filter(Sale.date < end_dt)

    rows = query.all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['Sale ID', 'Date', 'Item', 'Quantity', 'Customer', 'Payment', 'Net Total'])
    for sale in rows:
        writer.writerow([
            sale.id,
            sale.date.strftime('%Y-%m-%d %H:%M') if sale.date else '',
            sale.item,
            sale.quantity,
            sale.customer.name if sale.customer else '',
            (sale.payment_method or 'cash').title(),
            f"{float(sale.net_total or 0):.2f}",
        ])

    response = make_response(buffer.getvalue())
    filename_parts = ['sales']
    if start_str:
        filename_parts.append(start_str)
    if end_str:
        filename_parts.append(end_str)
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f"attachment; filename={'_'.join(filename_parts)}.csv"
    return response


@sales_bp.route('/sell', methods=['POST'])
@login_required
def sell():
    lock = Setting.query.filter_by(key='sales_lock_date').first()
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    if lock and lock.value == today_str and not (session.get('role') == 'admin' or session.get('admin')):
        flash('Sales are locked for today. An administrator must unlock before recording new sales.', 'warning')
        return redirect(url_for('sales.index'))

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
        net_total=net_total,
        invoice_number=next_invoice_number()
    )
    db.session.add(sale)
    db.session.flush()

    if sale_type == 'udhar':
        credit_name = customer.name if customer else customer_name
        if not credit_name:
            return 'Customer required for udhar', 400
        db.session.add(Credit(
            customer_id=customer.id if customer else customer_id,
            customer_name=credit_name,
            item=item.name,
            quantity=quantity,
            total=net_total,
            status='unpaid',
            reminder_phone=(customer.phone if customer and customer.phone else None)
        ))

    audit_details = {
        'item': item.name,
        'quantity': quantity,
        'invoice_number': sale.invoice_number,
    }
    if voice_transcript:
        audit_details['voice_transcript'] = voice_transcript

    log_event(
        action='sell',
        resource_type='sale',
        resource_id=sale.id if sale.id else None,
        before=None,
        after=audit_details
    )

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
    invoice_no = sale.invoice_number or f"{sale_id:05d}"

    body = (
        f'Dear {customer.name},\n\n'
        f'Your invoice {invoice_no} is ready.\n'
        'You can download it from your account.\n\n'
        'Thank you for shopping with us.'
    )
    send_mail(customer.email, f'Invoice {invoice_no}', body)

    log_event(
        action='send_invoice_email',
        resource_type='sale',
        resource_id=sale_id,
        before=None,
        after={'sale_id': sale_id, 'to': customer.email}
    )
    db.session.commit()

    return redirect(url_for('sales.index'))
