# Mobile Parity (Android First)

Status: `scaffolding`

## North Star
Deliver Android parity (with iOS roadmap) offering offline-first sales, inventory, and assistant experiences.

## Key Tracks
- **Design system** – responsive components, navigation, theming parity with web.
- **Sync APIs** – token auth, delta endpoints, conflict resolution guidance.
- **Device capabilities** – barcode/QR scanning, camera receipts, push notifications.
- **Launch plan** – beta program, crash reporting, Play Store assets.

## Current Progress
- `/api` blueprint with token-based login, logout, and heartbeat.
- Items, customers, recent sales, and sale creation endpoints aligned with existing business rules.

## Next Actions
- Add delta sync cursors + pagination for large datasets.
- Introduce offline queue endpoints for credit and expense capture.
- Harden API rate limiting and monitoring.

## Blockers
- Event-driven sync architecture finalization.
