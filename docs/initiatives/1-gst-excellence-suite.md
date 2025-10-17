# GST Excellence Suite

Status: `scaffolding`

## North Star
Deliver end-to-end GST compliance: e-invoices, e-way bills, multi-location GST profiles, and automated reconciliation with GSTN data.

## Current Progress
- Core data scaffolding shipped (`ShopLocation`, `Sale` GST columns, `EInvoiceSubmission` log).
- Compliance blueprint + service facade in place (`/compliance/...` routes with stubbed provider calls).

## Next Milestones
1. **Provider integration** – wire ClearTax/NIC sandbox, handle authentication refresh, map API payload from invoices.
2. **UI surface** – sales detail page compliance badges, retry controls, submission history timeline.
3. **Reconciliation workflow** – nightly job to import GSTN data, diff viewer, override/notes.
4. **Schema hardening** – Alembic migrations + background job queue (Celery/APScheduler task wrappers).

## Dependencies
- Credentials (`GST_*` env vars) per environment.
- Background job executor (current APScheduler may need queue + retry strategy).
- Secure storage for signed JSON payloads.
