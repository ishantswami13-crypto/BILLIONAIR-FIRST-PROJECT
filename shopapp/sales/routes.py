import csv
import io
import json
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from flask import (Blueprint, current_app, flash, make_response, redirect, render_template,
                   request, send_file, session, url_for)
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import (AuditLog, Credit, Customer, EInvoiceSubmission, Expense, Item, PaymentIntent,
                      PaymentTransaction, Sale, SaleItem, Setting, ShopProfile)
from ..utils.decorators import login_required
from ..utils.audit import log_event
from ..utils.invoices import next_invoice_number
from ..utils.mail import send_mail
from ..utils.pdfs import create_invoice_pdf
from ..utils_gst import calc_gst
from ..compliance.services import GSTIntegrationError, get_gst_service
from ..payments import get_payments_service
from ..pdf_service import render_sale_pdf

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

    item_rows = Item.query.order_by(Item.name.asc()).all()
    items = [
        (item.id, item.name, float(item.price or 0), int(item.current_stock or 0))
        for item in item_rows
    ]
    customer_rows = Customer.query.order_by(Customer.name.asc()).all()
    customers = [
        (customer.id, customer.name, customer.phone or 'N/A')
        for customer in customer_rows
    ]

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
    low_stock_items = (
        Item.query
        .filter(Item.current_stock <= func.coalesce(Item.reorder_level, 5))
        .order_by(Item.current_stock.asc(), Item.name.asc())
        .limit(12)
        .all()
    )
    low_stock = [
        (item.name, int(item.current_stock or 0))
        for item in low_stock_items
    ]

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

    recent_sales = (
        Sale.query.options(joinedload(Sale.customer))
        .order_by(Sale.date.desc())
        .limit(10)
        .all()
    )
    recent_sales_rows = [
        (
            sale.id,
            sale.date.strftime('%Y-%m-%d') if sale.date else '',
            sale.item,
            int(sale.quantity or 0),
            float(sale.net_total or sale.total or 0),
            sale.customer.name if sale.customer else 'Walk-in',
        )
        for sale in recent_sales
    ]


    return render_template(
        'index.html',
        items=items,
        customers=customers,
        sales=recent_sales_rows,
        today_count=today_count,
        today_rev=today_rev,
        unpaid_credits=unpaid_credits,
        low_stock_count=low_stock_count,
        low_stock=low_stock,
        todays_revenue=today_rev,
        outstanding_credit=unpaid_credits,
        tiny_chart=mini,
        chart_data=mini,
        streak_text=streak_text,
        active_plan=current_app.config.get('ACTIVE_PLAN'),
        app_version=current_app.config.get('APP_VERSION'),
        encryption_notice=current_app.config.get('DATA_ENCRYPTION_NOTICE'),
    )


@sales_bp.route('/sales')
@login_required
def history():
    from_str = request.args.get('from') or request.args.get('start')
    to_str = request.args.get('to') or request.args.get('end')
    customer_filter = request.args.get('customer')

    query = Sale.query.options(joinedload(Sale.customer))

    if from_str:
        try:
            from_dt = datetime.strptime(from_str, '%Y-%m-%d')
            query = query.filter(Sale.date >= from_dt)
        except ValueError:
            from_str = None

    if to_str:
        try:
            to_dt = datetime.strptime(to_str, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Sale.date < to_dt)
        except ValueError:
            to_str = None

    if customer_filter:
        try:
            query = query.filter(Sale.customer_id == int(customer_filter))
        except (TypeError, ValueError):
            customer_filter = None

    sales_rows = query.order_by(Sale.date.desc()).all()

    table_rows = [
        (
            sale.id,
            sale.date.strftime('%Y-%m-%d') if sale.date else '',
            sale.item,
            int(sale.quantity or 0),
            float(sale.net_total or sale.total or 0),
            sale.customer.name if sale.customer else 'Walk-in',
        )
        for sale in sales_rows
    ]

    total_revenue = round(sum(row[4] for row in table_rows), 2)
    total_qty = sum(row[3] for row in table_rows)
    avg_order = round(total_revenue / len(table_rows), 2) if table_rows else 0.0

    customers = [
        (customer.id, customer.name, customer.phone or 'N/A')
        for customer in Customer.query.order_by(Customer.name.asc()).all()
    ]

    return render_template(
        'sales/history.html',
        sales=table_rows,
        customers=customers,
        total_revenue=total_revenue,
        total_qty=total_qty,
        avg_order=avg_order,
    )


@sales_bp.route('/sales/<int:sale_id>')
@login_required
def detail(sale_id: int):
    sale = (
        Sale.query.options(
            joinedload(Sale.customer),
            joinedload(Sale.location),
        )
        .filter(Sale.id == sale_id)
        .first()
    )
    if not sale:
        flash('Sale not found.', 'warning')
        return redirect(url_for('sales.history'))

    submissions = (
        EInvoiceSubmission.query.filter_by(sale_id=sale_id)
        .order_by(EInvoiceSubmission.created_at.desc())
        .all()
    )

    payment_intents = (
        PaymentIntent.query.filter_by(sale_id=sale_id)
        .order_by(PaymentIntent.created_at.desc())
        .all()
    )
    providers = get_payments_service().list_providers()

    service = get_gst_service()
    gst_configured = service.is_configured()
    live_status = None
    if sale.irn and gst_configured:
        try:
            live_status = service.fetch_status(sale.irn)
        except GSTIntegrationError as exc:
            flash(f'Could not refresh GST status: {exc}', 'warning')

    return render_template(
        'sales/detail.html',
        sale=sale,
        submissions=submissions,
        gst_configured=gst_configured,
        live_status=live_status,
        payment_intents=payment_intents,
        payment_providers=[p for p in providers if p["enabled"]],
    )


@sales_bp.post('/sales/<int:sale_id>/gst/submit')
@login_required
def submit_gst(sale_id: int):
    sale = (
        Sale.query.options(
            joinedload(Sale.customer),
            joinedload(Sale.location),
        )
        .filter(Sale.id == sale_id)
        .first()
    )
    if not sale:
        flash('Sale not found.', 'warning')
        return redirect(url_for('sales.history'))

    service = get_gst_service()
    if not service.is_configured():
        flash('GST provider not configured. Add credentials in settings.', 'warning')
        return redirect(url_for('sales.detail', sale_id=sale_id))

    payload = {
        "invoice_number": sale.invoice_number,
        "date": sale.date.isoformat() if sale.date else None,
        "total": float(sale.net_total or sale.total or 0),
        "location_gstin": sale.location.gstin if sale.location else None,
        "customer": {
            "name": sale.customer.name if sale.customer else "Walk-in",
            "gstin": getattr(sale.customer, "gstin", None) if sale.customer else None,
        },
    }

    try:
        response = service.submit_einvoice(sale.id, payload)
    except GSTIntegrationError as exc:
        flash(f'GST submission failed: {exc}', 'danger')
        return redirect(url_for('sales.detail', sale_id=sale_id))

    submission = EInvoiceSubmission(
        sale_id=sale.id,
        status=response.get("status", "queued"),
        payload=json.dumps(payload),
        response=json.dumps(response),
    )

    sale.gst_status = submission.status or sale.gst_status
    sale.irn = response.get("irn") or sale.irn
    sale.ack_no = response.get("ack_no") or sale.ack_no
    ack_date_raw = response.get("ack_date")
    if ack_date_raw:
        try:
            sale.ack_date = datetime.fromisoformat(ack_date_raw)
        except ValueError:
            pass

    if response.get("eway_bill_no"):
        sale.eway_bill_no = response.get("eway_bill_no")
    if response.get("eway_valid_upto"):
        try:
            sale.eway_valid_upto = datetime.fromisoformat(response.get("eway_valid_upto"))
        except ValueError:
            pass

    db.session.add(submission)
    db.session.add(sale)
    db.session.commit()

    flash('GST submission queued.', 'success')
    return redirect(url_for('sales.detail', sale_id=sale_id))


@sales_bp.post('/sales/<int:sale_id>/payments')
@login_required
def create_payment_intent_for_sale(sale_id: int):
    sale = Sale.query.get(sale_id)
    if not sale:
        flash('Sale not found.', 'warning')
        return redirect(url_for('sales.history'))

    service = get_payments_service()
    provider_name = (request.form.get('provider') or 'razorpay').lower()
    provider = service.get_provider(provider_name)
    if not provider or not provider.enabled:
        flash('Selected provider is not available.', 'warning')
        return redirect(url_for('sales.detail', sale_id=sale_id))

    try:
        amount = float(request.form.get('amount') or sale.net_total or sale.total or 0)
    except (TypeError, ValueError):
        amount = float(sale.net_total or sale.total or 0)

    if amount <= 0:
        flash('Amount must be greater than zero.', 'warning')
        return redirect(url_for('sales.detail', sale_id=sale_id))

    profile = ShopProfile.query.get(1)

    intent = PaymentIntent(
        sale_id=sale.id,
        amount=amount,
        currency=(profile.currency if profile else 'INR'),
        provider=provider.name,
        status='pending',
        customer_reference=request.form.get('reference') or None,
    )
    db.session.add(intent)
    db.session.flush()

    txn = PaymentTransaction(
        intent=intent,
        provider=provider.name,
        status='created',
        amount=amount,
    )
    db.session.add(txn)
    db.session.commit()

    flash('Payment intent created.', 'success')
    return redirect(url_for('sales.detail', sale_id=sale_id))


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


@sales_bp.route('/restock', methods=['POST'])
@login_required
def restock():
    item_id_raw = request.form.get('item_id', '').strip()
    quantity_raw = request.form.get('quantity', '').strip()

    try:
        item_id = int(item_id_raw)
    except (TypeError, ValueError):
        flash('Select an item to restock.', 'error')
        return redirect(url_for('sales.index'))

    try:
        quantity = int(quantity_raw)
    except (TypeError, ValueError):
        flash('Enter a valid quantity.', 'error')
        return redirect(url_for('sales.index'))

    if quantity <= 0:
        flash('Quantity must be greater than zero.', 'error')
        return redirect(url_for('sales.index'))

    item = Item.query.get(item_id)
    if not item:
        flash('Item not found.', 'error')
        return redirect(url_for('sales.index'))

    before_stock = item.current_stock or 0
    item.current_stock = before_stock + quantity
    item.updated_at = datetime.utcnow()

    log_event(
        action='restock',
        resource_type='item',
        resource_id=item.id,
        before={'current_stock': before_stock},
        after={'current_stock': item.current_stock},
    )

    db.session.commit()
    flash(f'Added {quantity} to {item.name} stock.', 'success')
    return redirect(url_for('sales.index', restocked=1))


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

    profile = ShopProfile.query.get(1)

    seller_state_form = (request.form.get('seller_state') or '').strip().upper()
    seller_state = seller_state_form or 'DL'
    seller_gstin = profile.gst if profile and profile.gst else None

    buyer_state_form = (request.form.get('buyer_state') or request.form.get('customer_state') or '').strip().upper()
    if customer and buyer_state_form and not customer.state:
        customer.state = buyer_state_form
    buyer_state = buyer_state_form or (customer.state.upper() if customer and customer.state else seller_state)
    buyer_gstin = customer.gstin if customer and customer.gstin else (request.form.get('buyer_gstin') or None)

    items_payload = [{
        "description": item.name,
        "hsn_sac": getattr(item, 'hsn', None),
        "qty": quantity,
        "rate": item.price or 0,
        "gst_rate": item.gst_rate or 0,
        "tax_rate": item.gst_rate or 0,
    }]

    gst_breakdown = calc_gst(items_payload, seller_state, buyer_state)
    quant = Decimal("0.01")
    subtotal_decimal = gst_breakdown["subtotal"].quantize(quant, rounding=ROUND_HALF_UP)
    tax_total_decimal = gst_breakdown["tax_total"].quantize(quant, rounding=ROUND_HALF_UP)
    cgst_decimal = gst_breakdown["cgst"].quantize(quant, rounding=ROUND_HALF_UP)
    sgst_decimal = gst_breakdown["sgst"].quantize(quant, rounding=ROUND_HALF_UP)
    igst_decimal = gst_breakdown["igst"].quantize(quant, rounding=ROUND_HALF_UP)
    roundoff_decimal = gst_breakdown["roundoff"].quantize(quant, rounding=ROUND_HALF_UP)
    total_decimal = gst_breakdown["total"].quantize(quant, rounding=ROUND_HALF_UP)

    tax = float(tax_total_decimal)
    net_total = float(total_decimal)

    item.current_stock -= quantity

    location_id = None
    if profile:
        default_location = profile.default_location
        if not default_location and getattr(profile, "locations", None):
            default_location = profile.locations[0]
        if default_location:
            location_id = default_location.id

    sale = Sale(
        item=item.name,
        quantity=quantity,
        total=net_total,
        customer_id=customer.id if customer else customer_id,
        payment_method=payment_method,
        discount=discount,
        tax=tax,
        net_total=net_total,
        invoice_number=next_invoice_number(),
        location_id=location_id,
        subtotal=subtotal_decimal,
        tax_total=tax_total_decimal,
        roundoff=roundoff_decimal,
        cgst=cgst_decimal,
        sgst=sgst_decimal,
        igst=igst_decimal,
        seller_gstin=seller_gstin,
        buyer_gstin=buyer_gstin,
        seller_state=seller_state,
        buyer_state=buyer_state,
        place_of_supply=buyer_state or seller_state,
        notes=request.form.get('notes'),
    )
    db.session.add(sale)
    db.session.flush()

    breakdown = gst_breakdown["items"][0] if gst_breakdown["items"] else None
    line_total_decimal = (
        breakdown["gross"].quantize(quant, rounding=ROUND_HALF_UP) if breakdown else total_decimal
    )
    sale_item = SaleItem(
        sale_id=sale.id,
        description=item.name,
        hsn_sac=getattr(item, 'hsn', None),
        qty=Decimal(str(quantity)),
        rate=Decimal(str(item.price or 0)),
        gst_rate=Decimal(str(item.gst_rate or 0)),
        tax_rate=Decimal(str(item.gst_rate or 0)),
        line_total=line_total_decimal,
    )
    db.session.add(sale_item)

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

    redirect_url = url_for('sales.index')
    separator = '&' if '?' in redirect_url else '?'
    return redirect(f"{redirect_url}{separator}celebrate=1")


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


@sales_bp.route('/invoice/pdf')
@login_required
def invoice_pdf_v2():
    sale_id = request.args.get('id', type=int)
    if not sale_id:
        return {"error": "sale id required"}, 400

    sale = (
        Sale.query.options(joinedload(Sale.line_items), joinedload(Sale.customer))
        .filter_by(id=sale_id)
        .first()
    )
    if not sale:
        return {"error": "sale not found"}, 404

    items = sale.line_items or [sale]
    customer = getattr(sale, "customer", None)
    pdf_bytes, filename = render_sale_pdf(sale, items, customer)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
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
