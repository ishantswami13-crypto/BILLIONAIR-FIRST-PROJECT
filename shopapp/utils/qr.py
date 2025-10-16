from __future__ import annotations

import base64
import io

import qrcode
from qrcode.constants import ERROR_CORRECT_M


def generate_qr_image(data: str, box_size: int = 8, border: int = 4):
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    if hasattr(image, "get_image"):
        # PillowImage returns a wrapper that requires explicit extraction.
        image = image.get_image()
    return image


def qr_to_base64(data: str) -> str:
    if not data:
        return ""
    image = generate_qr_image(data)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")
