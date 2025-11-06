# SuperApp v2 — Flask + SQLAlchemy + JWT

## Quick Start
1) Create venv & install:


python -m venv .venv

Windows:

.venv\Scripts\activate

macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

2) Copy env:


cp .env.example .env

3) Run:


python manage.py

4) Flow (JWT):
- POST /api/auth/register -> get token
- Use Authorization: Bearer <token>
- POST /api/merchant/stores
- POST /api/inventory/products
- POST /api/sales/customers
- POST /api/sales/invoice
- POST /api/payments/collect -> upi_uri + qr base64
- POST /api/payments/webhook/mock-paid
