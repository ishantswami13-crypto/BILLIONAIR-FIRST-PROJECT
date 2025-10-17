# Smart Inventory & Procurement

Status: `scaffolding`

## Mission
Build predictive inventory, automated purchase ordering, and supplier collaboration tools.

## Focus Areas
- Supplier master + purchase orders + costing (FIFO/average).
- Forecasting pipeline (Prophet/stat models) driving alerts.
- Aging & slow-mover dashboards, markdown suggestions.
- Barcode label generation and scanning, CSV import/export refresh.

## Progress
- Supplier directory and draft purchase order creation are live via `/inventory/suppliers` and `/inventory/reorder`.
- Reorder planner surfaces low-stock items with suggested quantities and generates draft POs in one click.
- Purchase order console allows issuing and receiving orders while auto-updating stock.

## Next
- Extend lifecycle with approvals, partial receipts, and invoice reconciliation + costing.
- Introduce demand forecasting + alerts, plus supplier-facing share/export options.

## Dependencies
- Analytics warehouse strategy.
- Notification channels for alerts.
