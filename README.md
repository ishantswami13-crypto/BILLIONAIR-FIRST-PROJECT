# ShopApp SaaS

End-to-end shop management suite (billing, inventory, customers, credits/udhar, reports) built with Flask. The project ships with a Docker/Postgres production stack and a lightweight SQLite-based developer setup.

## Requirements

- Python 3.12+
- (Optional) Docker Desktop for the container stack
- Google/Gmail app password if you plan to send OTP or report emails

## Environment configuration

The repository contains two dotenv templates:

- .env – defaults for Docker/Postgres deployments (web talks to the db service)
- .env.local – overrides for local development. This file is loaded automatically **after** .env when you run the app on your machine.

Typical .env.local contents:

`
DATABASE_URL=sqlite:///shop.db
FLASK_ENV=development
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=admin123
DEFAULT_ADMIN_EMAIL=admin@example.com
MAIL_SENDER=
MAIL_PASSWORD=
`

Keep .env.local out of source control (the provided .gitignore already ignores it).

## Email transport options

- Default mode (`MAIL_TRANSPORT=smtp`) uses classic SMTP with `MAIL_SENDER` and `MAIL_PASSWORD` (for Gmail this should be an app password).
- Set `MAIL_TRANSPORT=google` to send via the Gmail API instead. Place your OAuth `credentials.json` and `token.pickle` in the project root (or point the env vars elsewhere) and make sure the token includes the `https://www.googleapis.com/auth/gmail.send` scope.
- If the Gmail API send fails the code silently falls back to SMTP when those credentials are still present, so scheduled jobs keep running.

## Run with Docker (Postgres + Gunicorn)

`ash
cp .env.example .env          # adjust SMTP + secrets as needed
docker compose up --build -d
docker compose exec web flask db upgrade
docker compose exec web flask seed-admin \
  --username admin --password change_me --email admin@example.com
`

The marketing site is available at <http://localhost:8000/> and the authenticated dashboard lives at <http://localhost:8000/app/>.

## Run locally without Docker (SQLite + Flask dev server)

`powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate
pip install -r requirements.txt
flask --app manage.py run
`

`ash
# macOS / Linux
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app manage.py run
`

- The app now auto-creates all tables and seeds a default admin using the values from the config (DEFAULT_ADMIN_*).
- Visit <http://127.0.0.1:5000/> for the landing page and <http://127.0.0.1:5000/app/> for the dashboard. Log in with the default admin credentials above and rotate them immediately. Change the password immediately from the UI or by rerunning lask seed-admin with new values.

## Recent improvements

- Automatic loading of `.env.local` overrides for painless local development.
- On startup the app creates missing tables and seeds a default shop profile + admin user.
- Added analytics hooks (GA4 + Mixpanel), plan-aware feature flags, and a `/settings/branding` admin page for GST-ready invoices with logo/signature support.
- Role-based access with owner/cashier/accountant invites, device session management, and multi-device support.
- Expense categories now support colour-coded tags, keyword auto-suggestions, and a dedicated analytics breakdown.
- Inventory heuristics now surface reorder prompts, slow-mover alerts, and high-demand warnings on the analytics dashboard.
- Payment provider webhooks now land in a reconciliation console with retry controls and manual matching to invoices.
- AI assistant dashboard for quick Q&A with conversation export.
- Automated WhatsApp reminders for outstanding credit (udhar) with opt-out controls and manual trigger.
- Nightly reports now lock the sales ledger until an admin overrides the lock from the settings page.
- Connect Hub ships a QR signage generator for payment/review links plus printable PDF signage.

## Background jobs

APScheduler runs two tasks while the server is up:

1. `daily_report.send_daily_report` – email summary at 22:00 (UTC).
2. `drive_backup.backup_to_drive` – Google Drive backup at 23:59 (UTC).

Both require valid SMTP credentials and Google API tokens (`credentials.json`, `token.pickle`). If those files/credentials are absent, the jobs will safely no-op.

## Analytics & feature gating

- Set `GA_MEASUREMENT_ID` to wire Google Analytics 4; the base layout includes the gtag snippet automatically.
- Set `MIXPANEL_TOKEN` to enable event tracking (a helper `track(event, props)` is exposed globally).
- Use `DAILY_REPORT_EMAIL` to override who receives the nightly summary (defaults to the admin email).
- Feature access is controlled via plan flags (`shopapp/plans.py`). Templates can call `feature_enabled('feature.key')`, and server code can import `feature_enabled` from `shopapp.utils.feature_flags`.

## AI assistant

- Visit `/assistant` to spin up a fresh chat session (each visit logs a new conversation).
- Ask about revenue, expenses, stock levels, or outstanding credit. Responses use the last 90 days of analytics.
- Export historical chats as JSON via the "Export" button.

## WhatsApp credit reminders

- Configure `WHATSAPP_TOKEN` + either `WHATSAPP_INSTANCE_ID` or a custom `WHATSAPP_API_URL`.
- Default country code falls back to `+91`; override via `WHATSAPP_DEFAULT_COUNTRY_CODE`.
- Reminders run daily at 18:00 UTC; adjust cadence with `WHATSAPP_REMINDER_COOLDOWN_HOURS`.
- Manage outstanding ledger and opt-outs at `/credits`.
- Trigger manually via `flask credits-send-reminders` if needed.

## Architecture notes

- Smart Connect design details and offline/hybrid strategy live in `docs/offline-architecture.md`.

## Troubleshooting

| Symptom | Fix |
| ------- | --- |
| OperationalError: could not translate host name "db" when running locally | Ensure .env.local points to sqlite:///shop.db. Remove/rename the Postgres DATABASE_URL value or run through Docker. |
| Login page refuses credentials | Confirm the default admin values in .env.local and rerun lask seed-admin if you changed them. |
| Emails/OTP are not delivered | Supply MAIL_SENDER + MAIL_PASSWORD (Gmail app password) or switch to `MAIL_TRANSPORT=google` with credentials. For a manual fallback, run `flask otp-latest` to view the most recent code. |
| Sales locked after nightly report | Visit `/settings/branding` as an admin and click “Override & unlock” to reopen the day. |

Feel free to extend the SQLAlchemy models and create Alembic migrations if you need production-grade schema evolution.

## Branding & invoices

- Update business identity, colours, and invoice prefix at /settings/branding.
- Upload signature and watermark assets for GST-compliant invoices.
- Invoice PDFs now carry auto-generated numbers and branding details.

## Marketing site, payments, and waitlist

- The marketing landing page now lives at `/landing` (alias `/marketing`). The root `/` redirects 
  authenticated users to `/app/` and everyone else to `/login`.
- Configure the landing copy via these environment variables (see `.env` / `.env.example`):
  - `PRODUCT_NAME`, `PRODUCT_TAGLINE`, `DEMO_GIF_URL`
  - `PAYMENT_LINK` **or** `STRIPE_CHECKOUT_URL` / `RAZORPAY_PAYMENT_LINK`
  - `WAITLIST_URL`
- To embed a Google Form waitlist, share the public form URL (`.../viewform`) and drop it into `WAITLIST_URL`. The app automatically switches to the embeddable `?embedded=true` version. Notion or other tools still open in a new tab.
- The landing page now highlights plan tiers (Free / Pro / Enterprise), testimonials, and the ShopApp Cloud trust badge with encryption notice.

### Configure Stripe or Razorpay buttons

1. Create a Payment Link (Stripe Dashboard ▸ Payments ▸ Payment links) or a Razorpay Payment Button.
2. Copy the hosted checkout URL and place it in `PAYMENT_LINK`. The landing page will surface a "Buy credits" button.
3. Optionally keep both Stripe and Razorpay links around; the app falls back to whichever value is present.
4. Redeploy/restart the service so the new environment value is picked up.

### Hook up a waitlist form

- Google Forms: paste the `viewform` URL into `WAITLIST_URL`; the embedded iframe will render automatically.
- Notion or Typeform: paste the public share link. Visitors are taken to the hosted form in a new tab.
- Support email defaults to `MAIL_SENDER`; override if you prefer a separate inbox.

## Free hosting playbook

### Render (free web service)

1. Push your repo and connect Render. It detects `render.yaml` that provisions a free web service.
2. Render builds with `pip install -r requirements.txt` and starts with `gunicorn app:app`.
3. Add the env vars above plus `DATABASE_URL` (Render Postgres) or reuse SQLite via persistent disk.
4. Health check endpoint: `/healthz`.

### Railway

1. Run `railway up` (or use the dashboard) and point it at this repo.
2. Railway reads the `Procfile` (`web: gunicorn app:app`) and mirrors your `.env` values.
3. Mount a persistent volume if you want to keep the SQLite file, or wire a managed Postgres add-on.

### Vercel (Python serverless)

1. Install the Vercel CLI, run `vercel login`, then `vercel` inside the project.
2. The included `vercel.json` deploys `app.py` via the `@vercel/python` runtime.
3. Add environment variables in the Vercel dashboard. Background schedulers do not run in serverless mode, so scheduled reports/backups require a Render/Railway deployment or an external cron.
4. If you need health checks, target `/healthz`.


