# Embedded Payments Stack

Status: `scaffolding`

## Objective
Enable seamless UPI/QR and card acceptance with automated ledger reconciliation and cash drawer controls.

## Workstreams
- Payment intent schema + settlement ledger.
- Razorpay/Stripe integration (checkout + webhooks).
- Cash POS UI (tender types, drawer counts, variance reports).
- Merchant onboarding + KYC capture flows.

## Progress
- Core models (`PaymentIntent`, `PaymentTransaction`) added with API endpoints for provider listing and intent creation.
- Provider facade loads Razorpay/Stripe credentials from config for future gateway wiring.
- Webhook endpoints capture provider callbacks and hydrate transaction records.
- Admin dashboard at `/payments/intents/dashboard` visualises recent intents and provider status.
- Sale detail page now supports creating intents and reviewing payment status inline.

## Next
- Implement provider-specific clients to generate checkout links/UPI QR codes.
- Handle webhook callbacks and reconciliation reporting.
- Extend POS UI for tender selection, settlements, and cash drawer audits.

## Pre-reqs
- PCI-compliant storage decisions.
- Webhook reliability (signing secrets, retries, monitoring).
