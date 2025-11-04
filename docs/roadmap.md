# Evara Pro Roadmap

This roadmap breaks the requested upgrades into manageable phases and documents the implementation detail required for each.

## No.1 Initiative — Competitive Feature Blitz

### 1. GST Excellence Suite
- **Scope:** e-invoice + e-way bill APIs, multi-branch GST profiles, automated GSTN reconciliation dashboard.
- **Key tasks:**
  - Model updates for GST identifiers (IRN, AckNo, transport details) and per-location GSTIN storage.
  - Service layer integrating NIC sandbox + fallback vendor (ClearTax/API aggregator) with retry queue.
  - Reconciliation worker comparing uploaded GSTR-1/2A data, flag discrepancies, manual override UI.
  - Compliance UX: status badges on invoices, download signed JSON/Ledger, compliance checklist wizard.
- **Dependencies:** finalize API provider credentials, background job queue hardening, signing certificate handling.

### 2. Mobile Parity (Android-first, iOS roadmap)
- **Scope:** Flutter/React Native client, offline-first sync, camera-based item capture, push notifications.
- **Key tasks:**
  - Mobile design system aligned with existing glassmorphism theme, state machines for onboarding/login.
  - Sync layer: REST/GraphQL endpoints for items, invoices, credits; conflict resolution policy.
  - Native features: barcode scanning, receipt share intent, on-device analytics cards.
  - Distribution: Play Store beta track, Crashlytics/Sentry instrumentation, OTA update pipeline.
- **Dependencies:** public API authentication (token refresh), sync-ready backend endpoints, CDN for assets.

### 3. Embedded Payments Stack
- **Scope:** UPI/QR, card gateway (Razorpay/Stripe), cash drawer audit, automatic ledger posting.
- **Key tasks:**
  - Payment intent schema, linking sales invoices to transaction records, partial payment support.
  - Webhooks + reconciliation UI for success/failure, dispute handling workflow, payout tracking.
  - QR catalogue (static/dynamic), POS screen for tender types, cash drawer open/close logs.
  - Merchant onboarding UX with KYC capture, compliance alerts (daily settlement report).
- **Dependencies:** payment provider accounts, PCI-compliant storage strategy, webhook security audit.

### 4. Premium Invoicing & Branding
- **Scope:** bilingual templates, per-customer branding presets, thermal printer layouts, subscription billing.
- **Key tasks:**
  - Template engine upgrades (Jinja blocks + CSS tokens), localized number/currency formatting.
  - Customer-specific invoice settings (language, tax inclusive/exclusive, delivery notes).
  - Thermal print integration (ESC/POS, Sunmi handheld), print preview fine-tuning.
  - Recurring invoice scheduler, autopay reminders, deferred revenue reports.
- **Dependencies:** localization framework, asset CDN, recurring billing engine under payments stack.

### 5. Smart Inventory & Procurement
- **Scope:** supplier portal, automated purchase orders, stock aging, demand forecast, barcode readiness.
- **Key tasks:**
  - Supplier + purchase order models, backordered quantity tracking, costing (FIFO/average).
  - Forecast engine (Prophet/stat models) seeded from sales history, alert thresholds.
  - Inventory aging report, slow mover heatmap, markdown suggestions.
  - Barcode/QR generation & scanning, label printing integration, CSV import/export improvements.
- **Dependencies:** analytics warehouse, job scheduling enhancements, supplier communication channel.

### 6. Credit & Finance Flywheel
- **Scope:** UPI repayments, lending partnerships, credit scoring, payroll onboarding.
- **Key tasks:**
  - Credit ledger overhaul with risk scores, reminder cadence optimizer.
  - Embedded finance integrations (cashflow-based loan offers), consent + compliance screens.
  - Payroll module (staff profiles, working hours, salary disbursement via UPI).
  - Finance insights dashboard (DSO trends, repayment funnels, risk alerts).
- **Dependencies:** payments stack, analytics pipeline, partner APIs, legal/compliance review.

### 7. AI, Automation & Voice Edge
- **Scope:** mobile AI assistant, anomaly detection, voice-to-invoice, workflow automation recipes.
- **Key tasks:**
  - Extend assistant to mobile with push notifications, saved queries, contextual insight cards.
  - Anomaly detection jobs flagging suspicious transactions, expense variance alerts.
  - Voice dictation pipeline (speech-to-text, entity extraction) feeding POS flow.
  - Automation builder (if-this-then-that) for stock, expenses, customer engagement triggers.
- **Dependencies:** model hosting infra, event streaming, robust logging/observability.

### 8. Growth Flywheel & CRM
- **Scope:** referrals, loyalty, campaigns, multi-branch HQ analytics.
- **Key tasks:**
  - Referral incentive logic, invite tracking, co-marketing assets.
  - Loyalty program (points, tiers, rewards catalog), redemption workflows.
  - Campaign manager for SMS/WhatsApp/email with segmentation and performance analytics.
  - Multi-branch dashboards, consolidation reports, HQ approvals workflow.
- **Dependencies:** communications providers, consent management, analytics warehouse.

## Phase 0 - Foundation & Planning
- **Documentation pack**
  - Author feature specs for invoices, analytics, automation, and security modules.
  - Sketch high-level user flows (login -> dashboard -> reports, POS -> invoice, admin -> settings) referencing current UI components.
  - Capture API surface area required for the assistant, reminders, and webhook integrations.
- **Schema review & migration backlog**
  - Inventory missing columns (for example `users.is_admin`, `sales.invoice_number`, `audit_log.before_state`).
  - Document new tables (`plans`, `plan_features`, `assistant_sessions`, `assistant_messages`, `reminder_log`).
  - Decide the sequencing for Alembic migrations and rollout order (dev -> staging -> production).
- **Feature gating strategy**
  - Define plan tiers (Free / Pro / Enterprise) and map features to each tier.
  - Decide on runtime checks (decorators, template helpers) tied to `session['plan']` or an organisation record.
  - Outline admin overrides, trials, and environment fallback behaviour.

## Phase 1 - Professional Trust Layer
- GST-ready invoices with auto numbering, signature/watermark support, PDF delivery, and branded email templates.
- Shop branding controls (logo upload, invoice prefix, primary/secondary colours) surfaced in settings and stored per shop.
- Enhanced audit log capturing CRUD operations with before/after snapshots, IP/device metadata, and diff view UI.
- End-of-day lock that freezes sales/expenses after the nightly report, including an admin override workflow with rationale capture.

## Phase 2 - Money & Insight Layer
- Profit vs. expense analytics (daily/weekly/monthly) with Chart.js visualisations, drill-down tables, and CSV exports.
- Expense categorisation (rules-based with optional AI suggestions) plus category management UI and bulk re-categorisation tools.
- Sales heatmap (best-selling hours) and customer lifetime value leaderboard cards surfaced on dashboard and reports.
- Recommendation engine MVP using inventory/sales heuristics (reorder prompts, slow-mover alerts, bundle opportunities).

## Phase 3 - Automation & Assistant Layer
- Voice command POS entry using browser Speech-to-Text (already shipped) with transcript logging and manual fallback.
- AI chat assistant (revenue, expense, inventory queries) with conversation log, export, and permissions.
- Automated WhatsApp reminders for outstanding credit customers, including opt-out, scheduling, and delivery status.

## Phase 4 - Smart Connect Layer *(shipped in v4.0)*
- Role-based multi-device access (owner, cashier, accountant) with granular permissions, invites, and session management. See `/settings/access`.
- Architecture notes for an offline-ready hybrid mode (service worker caching, background sync queue, conflict resolution policy). Captured in `docs/offline-architecture.md`.
- Webhook endpoints for payment providers plus transaction reconciliation UI with retry logs and manual matching (`/settings/connect`).
- QR code generator for payment/review links, printable signage, and shareable PDFs (Connect Hub signage tools).

## Phase 5 - Premium UI/UX & Business Model
- Side navigation and glassmorphism redesign with shimmer loaders, responsive breakpoints, and keyboard/focus states.
- Animated dashboards using Chart.js/Recharts with skeleton loaders, saved filters, and printable layouts.
- Subscription plan metadata (Free / Pro / Enterprise) with feature gating, upsell modals, and trial handling.
- Compliance cues: "Verified by Evara Cloud", AES-256 notice, SOC-readiness badge across app and landing experiences.

## Phase 6 - Social Proof & Authority
- Login banner "Trusted by 500+ businesses" with rotating client logos and CTA to case studies.
- Landing page testimonials and case studies section (cards, embedded videos, CTA buttons).
- Dashboard footer "Powered by Evara Cloud • v1.x" with support, terms, and privacy links.

## Phase 7 - Audit & Security Enhancements
- Comprehensive activity log export and "Data export to CA" bundle with bulk PDF/CSV generation.
- Drive backup retention (keep last seven versions) with ZIP packaging and a purge command.
- Post-report sales lock enforcement and admin override workflow with full audit trail.

## Bonus Ideas
- Time-based greetings and profit highlights.
- Mascot/assistant avatar for the chat module.
- Referral rewards program and loyalty tracking.
- Desktop offline client (Electron) planning doc.
