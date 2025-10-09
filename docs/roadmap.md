# ShopApp Pro Roadmap

This roadmap breaks the requested upgrades into manageable phases and documents the implementation detail required for each.

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

## Phase 4 - Smart Connect Layer
- Role-based multi-device access (owner, cashier, accountant) with granular permissions, invites, and session management.
- Architecture notes for an offline-ready hybrid mode (service worker caching, background sync queue, conflict resolution policy).
- Webhook endpoints for payment providers plus transaction reconciliation UI with retry logs and manual matching.
- QR code generator for payment/review links, printable signage, and shareable PDFs.

## Phase 5 - Premium UI/UX & Business Model
- Side navigation and glassmorphism redesign with shimmer loaders, responsive breakpoints, and keyboard/focus states.
- Animated dashboards using Chart.js/Recharts with skeleton loaders, saved filters, and printable layouts.
- Subscription plan metadata (Free / Pro / Enterprise) with feature gating, upsell modals, and trial handling.
- Compliance cues: "Verified by ShopApp Cloud", AES-256 notice, SOC-readiness badge across app and landing experiences.

## Phase 6 - Social Proof & Authority
- Login banner "Trusted by 500+ businesses" with rotating client logos and CTA to case studies.
- Landing page testimonials and case studies section (cards, embedded videos, CTA buttons).
- Dashboard footer "Powered by ShopApp Cloud • v1.x" with support, terms, and privacy links.

## Phase 7 - Audit & Security Enhancements
- Comprehensive activity log export and "Data export to CA" bundle with bulk PDF/CSV generation.
- Drive backup retention (keep last seven versions) with ZIP packaging and a purge command.
- Post-report sales lock enforcement and admin override workflow with full audit trail.

## Bonus Ideas
- Time-based greetings and profit highlights.
- Mascot/assistant avatar for the chat module.
- Referral rewards program and loyalty tracking.
- Desktop offline client (Electron) planning doc.
