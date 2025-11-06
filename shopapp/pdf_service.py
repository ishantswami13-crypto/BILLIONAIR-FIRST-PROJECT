from io import BytesIO
from typing import Iterable, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def render_sale_pdf(sale, items: Iterable, customer: Optional[object] = None) -> tuple[bytes, str]:
    """Render a GST-ready tax invoice PDF for the given sale."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=24,
        leftMargin=24,
        topMargin=24,
        bottomMargin=24,
    )
    styles = getSampleStyleSheet()
    elements = []

    invoice_number = getattr(sale, "invoice_number", None) or getattr(sale, "number", None) or sale.id
    elements.append(Paragraph(f"<b>TAX INVOICE</b> &nbsp;&nbsp; #{invoice_number}", styles["Title"]))

    seller_line = (
        f"GSTIN: {getattr(sale, 'seller_gstin', '-') or '-'}"
        f" | State: {getattr(sale, 'seller_state', '-') or '-'}"
    )
    buyer_gstin = getattr(sale, "buyer_gstin", None)
    buyer_state = getattr(sale, "buyer_state", None)
    buyer_name = getattr(customer, "name", None) or getattr(sale, "customer_name", None) or "-"
    buyer_line = f"To: {buyer_name} | GSTIN: {buyer_gstin or '-'} | State: {buyer_state or '-'}"

    elements.append(Paragraph(seller_line, styles["Normal"]))
    elements.append(Paragraph(buyer_line, styles["Normal"]))
    elements.append(Spacer(1, 10))

    rows = [["S.No", "Description", "HSN/SAC", "Qty", "Rate", "GST %", "Amount"]]
    for index, item in enumerate(items, start=1):
        rate_value = getattr(item, "rate", getattr(item, "price", 0)) or 0
        gst_rate_value = getattr(item, "gst_rate", getattr(item, "tax_rate", 0)) or 0
        amount_value = getattr(item, "line_total", getattr(item, "total", 0)) or 0
        rows.append(
            [
                index,
                getattr(item, "description", None)
                or getattr(item, "name", None)
                or getattr(item, "item", ""),
                getattr(item, "hsn_sac", "") or getattr(getattr(item, "product", None), "hsn", "") or "",
                str(getattr(item, "qty", getattr(item, "quantity", 1))),
                f"{float(rate_value):.2f}",
                f"{float(gst_rate_value):.2f}",
                f"{float(amount_value):.2f}",
            ]
        )

    table = Table(rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 10))

    totals = [
        ["Subtotal", f"{float(getattr(sale, 'subtotal', 0) or 0):.2f}"],
        ["CGST", f"{float(getattr(sale, 'cgst', 0) or 0):.2f}"],
        ["SGST", f"{float(getattr(sale, 'sgst', 0) or 0):.2f}"],
        ["IGST", f"{float(getattr(sale, 'igst', 0) or 0):.2f}"],
        ["Round-off", f"{float(getattr(sale, 'roundoff', 0) or 0):.2f}"],
        ["Grand Total", f"{float(getattr(sale, 'total', None) or getattr(sale, 'net_total', 0) or 0):.2f}"],
    ]
    totals_table = Table(totals, colWidths=[120, 120], hAlign="RIGHT")
    totals_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, -1), (-1, -1), colors.whitesmoke),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ]
        )
    )
    elements.append(totals_table)

    if getattr(sale, "notes", None):
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(f"Notes: {sale.notes}", styles["Italic"]))

    doc.build(elements)
    return buffer.getvalue(), f"Invoice_{invoice_number}.pdf"
