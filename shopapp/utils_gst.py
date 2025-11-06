from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

D = lambda x: Decimal(str(x or 0))


def calc_gst(items: Iterable[dict], seller_state: str, buyer_state: str) -> dict:
    """Compute GST split for a list of items."""
    seller = (seller_state or "").strip().upper()
    buyer = (buyer_state or "").strip().upper()
    intra = seller == buyer and seller != ""

    subtotal = Decimal(0)
    cgst = Decimal(0)
    sgst = Decimal(0)
    igst = Decimal(0)
    breakdown = []

    for raw in items:
        qty = D(raw.get("qty", 1))
        rate = D(raw.get("rate", 0))
        gst_rate = D(raw.get("gst_rate", raw.get("tax_rate", 0)))
        base = qty * rate
        subtotal += base

        if intra:
            half = (base * gst_rate / Decimal(100)) / 2
            cgst += half
            sgst += half
            gross = base + (half * 2)
            breakdown.append(
                {
                    "base": base,
                    "gst_rate": gst_rate,
                    "cgst": half,
                    "sgst": half,
                    "igst": Decimal(0),
                    "gross": gross,
                }
            )
        else:
            ig = base * gst_rate / Decimal(100)
            igst += ig
            gross = base + ig
            breakdown.append(
                {
                    "base": base,
                    "gst_rate": gst_rate,
                    "cgst": Decimal(0),
                    "sgst": Decimal(0),
                    "igst": ig,
                    "gross": gross,
                }
            )

    tax_total = cgst + sgst + igst
    total = subtotal + tax_total
    total_rounded = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    roundoff = total_rounded - total

    return {
        "subtotal": subtotal,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "tax_total": tax_total,
        "total": total_rounded,
        "roundoff": roundoff,
        "intra": intra,
        "items": breakdown,
    }

