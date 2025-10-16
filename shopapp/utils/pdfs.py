import os
import io
from datetime import datetime
from pathlib import Path

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from ..extensions import db
from ..models import Customer, Sale, ShopProfile
from .qr import generate_qr_image


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

    primary_color = colors.HexColor(shop.primary_color) if shop and shop.primary_color else colors.HexColor('#0A2540')
    secondary_color = colors.HexColor(shop.secondary_color) if shop and shop.secondary_color else colors.HexColor('#62b5ff')

    invoice_number = sale.invoice_number or f"{sale.id:05d}"
    invoice_path = os.path.join(invoices_dir(), f'invoice_{invoice_number}.pdf')
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    brand = primary_color
    text_color = colors.HexColor('#333333')

    pdf.setFillColor(brand)
    pdf.rect(0, height - 100, width, 100, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont('Helvetica-Bold', 22)
    pdf.drawString(40, height - 60, shop_name)

    if shop and shop.logo_path:
        logo_path = Path(current_app.root_path) / shop.logo_path
        if logo_path.exists():
            try:
                pdf.drawImage(ImageReader(logo_path.open('rb')), width - 120, height - 90, width=80, height=50, mask='auto')
            except Exception:
                pass

    if shop and shop.watermark_path:
        watermark_path = Path(current_app.root_path) / shop.watermark_path
        if watermark_path.exists():
            try:
                pdf.saveState()
                pdf.translate(width / 2, height / 2)
                pdf.rotate(30)
                pdf.setFillAlpha(0.08)
                pdf.drawImage(ImageReader(watermark_path.open('rb')), -200, -150, width=400, height=300, mask='auto')
                pdf.restoreState()
            except Exception:
                pass

    pdf.setFillColor(text_color)
    pdf.setFont('Helvetica', 11)
    pdf.drawString(40, height - 130, 'Invoice summary')
    pdf.drawString(40, height - 148, f'Invoice: {invoice_number}')
    pdf.drawString(40, height - 166, f'Date: {sale.date.strftime("%d %b %Y %H:%M")}')
    if shop and shop.gst:
        pdf.drawString(40, height - 184, f'GSTIN: {shop.gst}')

    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(40, height - 210, 'Billed to:')
    pdf.setFont('Helvetica', 10)
    if customer:
        pdf.drawString(40, height - 226, customer.name)
        if customer.phone:
            pdf.drawString(40, height - 242, f'Phone: {customer.phone}')
        if customer.email:
            pdf.drawString(40, height - 258, f'Email: {customer.email}')
    else:
        pdf.drawString(40, height - 226, 'Walk-in customer')

    pdf.setFont('Helvetica-Bold', 10)
    table_top = height - 300
    pdf.drawString(40, table_top, 'Item')
    pdf.drawString(320, table_top, 'Qty')
    pdf.drawRightString(width - 80, table_top, 'Amount')

    pdf.setFont('Helvetica', 10)
    pdf.drawString(40, table_top - 16, sale.item)
    pdf.drawString(320, table_top - 16, str(sale.quantity))
    pdf.drawRightString(width - 80, table_top - 16, f'Rs {sale.total:,.2f}')

    subtotal = sale.net_total - sale.tax + sale.discount

    summary_y = table_top - 70
    pdf.setFont('Helvetica', 10)
    pdf.drawString(320, summary_y, 'Subtotal')
    pdf.drawRightString(width - 80, summary_y, f'Rs {subtotal:,.2f}')
    summary_y -= 16
    pdf.drawString(320, summary_y, 'Discount')
    pdf.drawRightString(width - 80, summary_y, f'Rs {sale.discount:,.2f}')
    summary_y -= 16
    pdf.drawString(320, summary_y, 'GST')
    pdf.drawRightString(width - 80, summary_y, f'Rs {sale.tax:,.2f}')
    summary_y -= 20
    pdf.setFont('Helvetica-Bold', 12)
    pdf.drawString(320, summary_y, 'Total')
    pdf.setFillColor(secondary_color)
    pdf.drawRightString(width - 80, summary_y, f'Rs {sale.net_total:,.2f}')
    pdf.setFillColor(text_color)

    if shop and shop.signature_path:
        signature_path = Path(current_app.root_path) / shop.signature_path
        if signature_path.exists():
            try:
                pdf.drawImage(ImageReader(signature_path.open('rb')), 40, 100, width=50 * mm, height=20 * mm, mask='auto')
                pdf.setFont('Helvetica', 9)
                pdf.drawString(40, 90, 'Authorised Signature')
            except Exception:
                pass

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


def create_signage_pdf(payment_url: str | None, review_url: str | None, shop: ShopProfile | None = None) -> str:
    shop = shop or ShopProfile.query.get(1)
    shop_name = (shop.name if shop and shop.name else "Your Shop").upper()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(reports_dir(), f"connect_signage_{timestamp}.pdf")

    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawCentredString(width / 2, height - 60, f"{shop_name} • SMART CONNECT")
    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(width / 2, height - 90, "Scan to pay or leave a review")

    def _draw_qr(label: str, url: str | None, center_x: float, top_y: float):
        if not url:
            return
        try:
            image = generate_qr_image(url, box_size=10, border=2)
            reader = ImageReader(image)
            size = 160
            pdf.drawImage(reader, center_x - size / 2, top_y - size, width=size, height=size)
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawCentredString(center_x, top_y - size - 20, label)
            pdf.setFont("Helvetica", 9)
            pdf.drawCentredString(center_x, top_y - size - 36, url)
        except Exception:
            pass

    column_spacing = width / 3
    start_x = column_spacing
    top = height - 150
    _draw_qr("Pay Digitally", payment_url, start_x, top)
    _draw_qr("Leave a Review", review_url, width - column_spacing, top)

    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(width / 2, 50, "Generated by ShopApp Connect")

    pdf.save()
    buf.seek(0)
    with open(path, "wb") as handle:
        handle.write(buf.getvalue())
    return path
