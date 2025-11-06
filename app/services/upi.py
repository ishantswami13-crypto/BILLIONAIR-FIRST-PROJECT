"""UPI Provider adapter. Starts with MOCK for local dev.
Switch to Razorpay/Cashfree later by implementing same interface.
"""
import base64
import io
import qrcode


class MockUPIProvider:
    @staticmethod
    def create_collect_request(payee_vpa: str, amount: float, txn_note: str, invoice_number: str) -> dict:
        upi_uri = f"upi://pay?pa={payee_vpa}&pn=Merchant&am={amount:.2f}&cu=INR&tn={txn_note}&tr={invoice_number}"
        img = qrcode.make(upi_uri)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return {"upi_uri": upi_uri, "qr_png_base64": b64}


def get_upi_provider(name: str):
    name = (name or "mock").lower()
    return MockUPIProvider()
