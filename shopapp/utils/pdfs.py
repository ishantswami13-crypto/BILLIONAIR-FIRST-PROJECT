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
    shop_name = shop.name if shop and shop.name else 'Evara'

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
    seller_gstin_value = sale.seller_gstin or (shop.gst if shop and shop.gst else None)
    seller_state_value = sale.seller_state or None
    if seller_gstin_value:
        pdf.drawString(40, height - 184, f'GSTIN: {seller_gstin_value}')
    if seller_state_value:
        pdf.drawString(40, height - 202, f'State: {seller_state_value}')
        text_offset = 220
    else:
        text_offset = 202

    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(40, height - text_offset, 'Billed to:')
    pdf.setFont('Helvetica', 10)
    if customer:
        pdf.drawString(40, height - (text_offset + 16), customer.name)
        cursor = text_offset + 32
        if customer.phone:
            pdf.drawString(40, height - cursor, f'Phone: {customer.phone}')
            cursor += 16
        if customer.email:
            pdf.drawString(40, height - cursor, f'Email: {customer.email}')
            cursor += 16
        if sale.buyer_gstin:
            pdf.drawString(40, height - cursor, f'GSTIN: {sale.buyer_gstin}')
            cursor += 16
        if sale.buyer_state:
            pdf.drawString(40, height - cursor, f'State: {sale.buyer_state}')
    else:
        pdf.drawString(40, height - (text_offset + 16), 'Walk-in customer')

    pdf.setFont('Helvetica-Bold', 10)
    table_top = height - 300
    pdf.drawString(40, table_top, 'Item')
    pdf.drawString(320, table_top, 'Qty')
    pdf.drawRightString(width - 80, table_top, 'Amount')

    pdf.setFont('Helvetica', 10)
    row_gap = 16
    y_cursor = table_top - row_gap
    if getattr(sale, "line_items", None):
        for line in sale.line_items:
            pdf.drawString(40, y_cursor, line.description or sale.item)
            pdf.drawString(320, y_cursor, str(line.qty or 0))
            pdf.drawRightString(width - 80, y_cursor, f'Rs {float(line.line_total or 0):,.2f}')
            y_cursor -= row_gap
    else:
        pdf.drawString(40, y_cursor, sale.item)
        pdf.drawString(320, y_cursor, str(sale.quantity))
        pdf.drawRightString(width - 80, y_cursor, f'Rs {sale.total:,.2f}')
        y_cursor -= row_gap

    subtotal_value = float(sale.subtotal or (sale.net_total - sale.tax + sale.discount))
    discount_value = float(sale.discount or 0)
    cgst_value = float(sale.cgst or 0)
    sgst_value = float(sale.sgst or 0)
    igst_value = float(sale.igst or 0)
    tax_total_value = float(sale.tax_total or sale.tax or 0)
    roundoff_value = float(sale.roundoff or 0)
    total_value = float(sale.total or sale.net_total or 0)

    summary_y = y_cursor - 24
    pdf.setFont('Helvetica', 10)
    pdf.drawString(320, summary_y, 'Subtotal')
    pdf.drawRightString(width - 80, summary_y, f'Rs {subtotal_value:,.2f}')
    summary_y -= row_gap
    if discount_value:
        pdf.drawString(320, summary_y, 'Discount')
        pdf.drawRightString(width - 80, summary_y, f'Rs {discount_value:,.2f}')
        summary_y -= row_gap
    if cgst_value or sgst_value:
        if cgst_value:
            pdf.drawString(320, summary_y, 'CGST')
            pdf.drawRightString(width - 80, summary_y, f'Rs {cgst_value:,.2f}')
            summary_y -= row_gap
        if sgst_value:
            pdf.drawString(320, summary_y, 'SGST')
            pdf.drawRightString(width - 80, summary_y, f'Rs {sgst_value:,.2f}')
            summary_y -= row_gap
    if igst_value:
        pdf.drawString(320, summary_y, 'IGST')
        pdf.drawRightString(width - 80, summary_y, f'Rs {igst_value:,.2f}')
        summary_y -= row_gap
    if not (cgst_value or sgst_value or igst_value):
        pdf.drawString(320, summary_y, 'GST')
        pdf.drawRightString(width - 80, summary_y, f'Rs {tax_total_value:,.2f}')
        summary_y -= row_gap
    if roundoff_value:
        pdf.drawString(320, summary_y, 'Round-off')
        pdf.drawRightString(width - 80, summary_y, f'Rs {roundoff_value:,.2f}')
        summary_y -= row_gap
    summary_y -= row_gap
    pdf.setFont('Helvetica-Bold', 12)
    pdf.drawString(320, summary_y, 'Total')
    pdf.setFillColor(secondary_color)
    pdf.drawRightString(width - 80, summary_y, f'Rs {total_value:,.2f}')
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
    pdf.drawCentredString(width / 2, 50, "Generated by Evara Connect")

    pdf.save()
    buf.seek(0)
    with open(path, "wb") as handle:
        handle.write(buf.getvalue())
    return path
