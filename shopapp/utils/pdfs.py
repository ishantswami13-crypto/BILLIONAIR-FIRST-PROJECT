import os
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from ..extensions import db
from ..models import Sale, Customer, Item, ShopProfile


def invoices_dir() -> str:
    path = os.path.join(os.getcwd(), 'invoices')
    os.makedirs(path, exist_ok=True)
    return path


def reports_dir() -> str:
    path = os.path.join(os.getcwd(), 'reports')
    os.makedirs(path, exist_ok=True)
    return path


def create_invoice_pdf(sale_id: int) -> str | None:
    sale = Sale.query.get(sale_id)
    if not sale:
        return None

    customer = Customer.query.get(sale.customer_id) if sale.customer_id else None
    shop = ShopProfile.query.get(1)
    shop_name = shop.name if shop and shop.name else 'ShopApp'

    invoice_path = os.path.join(invoices_dir(), f'invoice_{sale_id}.pdf')
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    brand = colors.HexColor('#0A2540')
    text_color = colors.HexColor('#333333')

    pdf.setFillColor(brand)
    pdf.rect(0, height - 100, width, 100, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont('Helvetica-Bold', 22)
    pdf.drawString(40, height - 60, shop_name)

    pdf.setFillColor(text_color)
    pdf.setFont('Helvetica', 11)
    pdf.drawString(40, height - 130, 'Invoice summary')
    pdf.drawString(40, height - 148, f'Sale ID: {sale.id}')
    pdf.drawString(40, height - 166, f'Date: {sale.date}')

    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(40, height - 198, 'Billed to:')
    pdf.setFont('Helvetica', 10)
    if customer:
        pdf.drawString(40, height - 214, customer.name)
        if customer.phone:
            pdf.drawString(40, height - 230, f'Phone: {customer.phone}')
        if customer.email:
            pdf.drawString(40, height - 246, f'Email: {customer.email}')
    else:
        pdf.drawString(40, height - 214, 'Walk-in customer')

    pdf.setFont('Helvetica-Bold', 10)
    pdf.drawString(40, height - 275, 'Item')
    pdf.drawString(320, height - 275, 'Qty')
    pdf.drawRightString(width - 80, height - 275, 'Amount')

    pdf.setFont('Helvetica', 10)
    pdf.drawString(40, height - 291, sale.item)
    pdf.drawString(320, height - 291, str(sale.quantity))
    pdf.drawRightString(width - 80, height - 291, f'Rs {sale.net_total:,.2f}')

    pdf.save()
    buf.seek(0)
    with open(invoice_path, 'wb') as handle:
        handle.write(buf.getvalue())
    return invoice_path


def create_zreport_pdf(summary: dict) -> str:
    path = os.path.join(reports_dir(), f"zreport_{summary['date']}.pdf")
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    pdf.setFont('Helvetica-Bold', 16)
    pdf.drawString(40, height - 50, f"Day Close - {summary['display_date']}")
    pdf.setFont('Helvetica', 12)
    pdf.drawString(40, height - 80, f"Revenue: Rs {summary['totals']['revenue']:,.2f}")
    pdf.drawString(40, height - 100, f"Transactions: {summary['totals']['transactions']}")

    y = height - 140
    pdf.setFont('Helvetica-Bold', 12)
    pdf.drawString(40, y, 'Payment split')
    y -= 20
    pdf.setFont('Helvetica', 10)
    for row in summary['payment_breakdown']:
        share = (row['amount'] / summary['payment_total'] * 100) if summary['payment_total'] else 0
        pdf.drawString(40, y, f"{row['method'].title()}: {row['transactions']} tx, Rs {row['amount']:,.2f} ({share:.1f}%)")
        y -= 16

    y -= 8
    pdf.setFont('Helvetica-Bold', 12)
    pdf.drawString(40, y, 'Top items')
    y -= 20
    pdf.setFont('Helvetica', 10)
    if not summary['top_items']:
        pdf.drawString(40, y, 'No items sold for the period')
        y -= 16
    else:
        for item in summary['top_items']:
            pdf.drawString(40, y, f"{item['item']}: {item['quantity']} pcs, Rs {item['amount']:,.2f}")
            y -= 16

    y -= 8
    pdf.setFont('Helvetica-Bold', 12)
    pdf.drawString(40, y, 'Udhar snapshot')
    y -= 20
    pdf.setFont('Helvetica', 10)
    pdf.drawString(40, y, f"Udhar today: {summary['udhar']['count']} tx, Rs {summary['udhar']['amount']:,.2f}")
    y -= 16
    pdf.drawString(40, y, f"Outstanding udhar: Rs {summary['udhar']['outstanding_total']:,.2f} across {summary['udhar']['outstanding_accounts']} accounts")

    pdf.save()
    buf.seek(0)
    with open(path, 'wb') as handle:
        handle.write(buf.getvalue())
    return path
