# Offline-Ready Architecture Notes

This document captures the planning notes for taking ShopApp into an offline-friendly, hybrid mode. The goal is to let store staff continue operating the POS, inventory, and credits modules on flaky or fully offline connections, then synchronise safely when connectivity returns.

## Objectives
- Keep the POS flow, expense logging, and credits ledger usable on mobile/tablet devices when the network drops.
- Cache the owner dashboard and assistant so read-only analytics remain visible offline (with stale data notice).
- Queue up write operations (sales, returns, credits, inventory adjustments) in the browser and replay them against the server once a connection is available.
- Provide deterministic conflict handling so owners can trust the recovered state without hidden overwrites.

## Progressive Web App shell
- Ship a dedicated service worker registered from `/app/service-worker.js`.
- Precache the authenticated shell: layout assets, CSS/JS bundles, fonts, voice POS assets, and the POS form HTML.
- Use `stale-while-revalidate` for dashboard/reports GET requests so cached charts appear instantly while the service worker fetches fresh data when online.
- Detect offline mode via the `navigator.onLine` API and broadcast updates to the UI (e.g. banner “Offline mode — logging locally”).

## Data caching strategy
- Maintain two caches:
  1. `shell-cache-v1` – static assets and critical HTML routes.
  2. `data-cache-v1` – JSON payloads for inventory, customers, expense categories, outstanding credits, and the latest analytics snapshot.
- For POST/PUT/DELETE requests the service worker should intercept and route to a background sync queue (see below).
- Evict cache entries older than 24 hours on service worker activate to prevent unbounded growth.

## Background sync queue
- Store queued mutations in IndexedDB (`shopapp_sync_queue`) with shape:
  ```json
  {
    "id": "uuid",
    "url": "/api/sales",
    "method": "POST",
    "payload": { ... },
    "created_at": "2025-10-10T07:15:00Z",
    "attempts": 0
  }
  ```
- When offline, POST/PUT requests return a synthetic response (`202 Accepted`) so the UI can proceed while logging audit breadcrumbs locally.
- Register a `sync` event (`navigator.serviceWorker.ready.then(sw => sw.sync.register('shopapp-sync'))`) that flushes the queue:
  1. Replay each request with exponential backoff (retry after 5, 15, 30 minutes).
  2. Persist server response metadata alongside the queued item for reconciliation UI (success vs. failure details).
- If the SyncManager API is unavailable, fall back to a `setInterval` ping managed from the page once network becomes reachable.

## Conflict resolution policy
- Every queued mutation includes the last-known record hash/timestamp (`etag`) from when the change was captured.
- The server compares the `If-Match` header with the current record:
  - **Match**: apply the change and return the new record state.
  - **Mismatch**: respond with `409 Conflict` and include both states. The client stores the conflict record locally and surfaces it in the reconciliation tab for manual review.
- For stock-sensitive operations (sales/inventory adjustments):
  - Prefer “append-only” ledger entries on the server; the client never overwrites stock counts directly.
  - When conflicts are detected, generate an audit entry that highlights the original offline payload and the server’s canonical values.

## Session handling
- Offline mode relies on long-lived session cookies. The new `user_sessions` table keeps device tokens so owners can revoke lost tablets remotely.
- Service worker should refuse to enqueue requests if the server responds with `401` once back online, forcing the user to re-authenticate and clearing the local queue.

## Observability & UX
- Add a “Sync centre” widget to `/settings/connect` that lists queued operations, last sync time, and conflict count.
- Push Mixpanel events (`offline_queue_add`, `offline_queue_flush`, `offline_conflict`) when tracking tokens are available to monitor adoption.
- Display a dismissible snackbar when operations successfully replay so staff know offline work landed in the cloud.

## Next steps
- Build the `/app/service-worker.js` asset with Workbox or a lightweight handcrafted implementation following the strategy above.
- Expose lightweight REST endpoints (`/api/sales`, `/api/returns`, `/api/credits`) that accept JSON payloads aligned with the queue format.
- Extend the reconciliation UI (Phase 4 deliverable) to also show offline conflict items alongside webhook alerts.
- Document support instructions in the README so shops know how to install the app to homescreen and understand offline limitations (e.g. assistant responses remain frozen until online).
