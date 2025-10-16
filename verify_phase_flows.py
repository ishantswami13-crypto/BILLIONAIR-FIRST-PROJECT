from __future__ import annotations

import json
from datetime import date, datetime

from shopapp import create_app
from shopapp.extensions import db
from shopapp.models import (
    ApiWebhook,
    Expense,
    ExpenseCategory,
    Sale,
    User,
    UserInvite,
    UserRole,
    UserSession,
    WebhookEvent,
)

app = create_app()
app.testing = True
client = app.test_client()
results: list[tuple[str, object]] = []

with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    assert admin, "Admin user missing"

    def get_or_create_category(name: str, color: str, keywords: str) -> ExpenseCategory:
        cat = ExpenseCategory.query.filter_by(name=name).first()
        if not cat:
            cat = ExpenseCategory(name=name, color=color, keywords=keywords)
            db.session.add(cat)
            db.session.commit()
        return cat

    cat_logistics = get_or_create_category('Logistics', '#62b5ff', 'shipping,delivery,courier')
    cat_supplies = get_or_create_category('Supplies', '#7cf29c', 'stationery,paper,ink')

    def create_expense(amount: float, notes: str, category: ExpenseCategory | None = None) -> Expense:
        exp = Expense.query.filter_by(notes=notes).first()
        if not exp:
            exp = Expense(
                date=date.today(),
                amount=amount,
                notes=notes,
                category=category.name if category else None,
                category_id=category.id if category else None,
            )
            db.session.add(exp)
            db.session.commit()
        return exp

    expense_a = create_expense(500.0, 'Shipping charges to FedEx')
    expense_b = create_expense(250.0, 'Printer paper restock', category=cat_supplies)
    expense_c = create_expense(300.0, 'Urgent delivery to client', category=None)

    sale = Sale.query.filter_by(invoice_number='UNITTEST-001').first()
    if not sale:
        sale = Sale(
            item='Test Widget',
            quantity=1,
            total=100.0,
            net_total=100.0,
            payment_method='cash',
            discount=0.0,
            tax=0.0,
            invoice_number='UNITTEST-001',
            date=datetime.utcnow(),
        )
        db.session.add(sale)
        db.session.commit()
        results.append(("seed_sale", sale.id))

    login_resp = client.post(
        '/login',
        data={'username': 'admin', 'password': 'admin123'},
        follow_redirects=True,
    )
    results.append(("login_status", login_resp.status_code))

    active_session = (
        UserSession.query.filter_by(user_id=admin.id, revoked_at=None)
        .order_by(UserSession.created_at.desc())
        .first()
    )
    assert active_session, "Expected active session after login"

    reassign_resp = client.post(
        '/expenses/reassign',
        data={
            'expense_ids': [str(expense_a.id), str(expense_c.id)],
            'bulk_category_id': str(cat_supplies.id),
        },
        follow_redirects=True,
    )
    results.append(("bulk_reassign_status", reassign_resp.status_code))

    refreshed_a = Expense.query.get(expense_a.id)
    refreshed_c = Expense.query.get(expense_c.id)
    results.append(("expense_a_category", refreshed_a.category))
    results.append(("expense_c_category", refreshed_c.category))

    refreshed_c.category = None
    refreshed_c.category_id = None
    db.session.commit()

    apply_resp = client.post(
        f'/expenses/{refreshed_c.id}/apply-suggestion',
        follow_redirects=True,
    )
    results.append(("apply_suggestion_status", apply_resp.status_code))
    refreshed_c = Expense.query.get(refreshed_c.id)
    results.append(("expense_c_suggested_category", refreshed_c.category))

    audit_resp = client.get('/admin/audit-log')
    results.append(("audit_log_status", audit_resp.status_code))
    audit_contains = 'expenses_bulk_reassign' in audit_resp.get_data(as_text=True)
    results.append(("audit_contains_bulk", audit_contains))

    access_page = client.get('/settings/access')
    results.append(("access_page_status", access_page.status_code))

    invite_email = f"tester+{int(datetime.utcnow().timestamp())}@example.com"
    invite_resp = client.post(
        '/settings/access/invite',
        data={'email': invite_email, 'role': 'cashier'},
        follow_redirects=True,
    )
    results.append(("invite_create_status", invite_resp.status_code))

    invite = UserInvite.query.filter_by(email=invite_email).first()
    results.append(("invite_created", bool(invite)))

    if invite:
        resend_resp = client.post(
            f'/settings/access/invite/{invite.id}/resend',
            follow_redirects=True,
        )
        results.append(("invite_resend_status", resend_resp.status_code))

        revoke_resp = client.post(
            f'/settings/access/invite/{invite.id}/revoke',
            follow_redirects=True,
        )
        results.append(("invite_revoke_status", revoke_resp.status_code))
    else:
        results.append(("invite_error_html", invite_resp.get_data(as_text=True)[:200]))

    role_resp = client.post(
        f'/settings/access/users/{admin.id}/role',
        data={'role': 'owner'},
        follow_redirects=True,
    )
    results.append(("update_role_status", role_resp.status_code))

    # Connect hub flows while session is active
    connect_page = client.get('/settings/connect', follow_redirects=True)
    results.append(("connect_page_status", connect_page.status_code))

    qr_resp = client.post(
        '/settings/connect/qr',
        data={
            'payment_url': 'https://pay.example.com/abc',
            'review_url': 'https://review.example.com/xyz',
        },
        follow_redirects=True,
    )
    results.append(("qr_preview_status", qr_resp.status_code))

    provider_slug = f"provider{int(datetime.utcnow().timestamp())}"
    webhook_create = client.post(
        '/settings/connect/webhooks',
        data={
            'provider': provider_slug,
            'event': 'payment.completed',
            'retry_window': '20',
        },
        follow_redirects=True,
    )
    results.append(("webhook_create_status", webhook_create.status_code))

    webhook = ApiWebhook.query.filter_by(provider=provider_slug, event='payment.completed').first()
    results.append(("webhook_created", bool(webhook)))

    if webhook:
        toggle_resp = client.post(
            f'/settings/connect/webhooks/{webhook.id}/toggle',
            follow_redirects=True,
        )
        results.append(("webhook_toggle_status", toggle_resp.status_code))

        rotate_resp = client.post(
            f'/settings/connect/webhooks/{webhook.id}/rotate',
            follow_redirects=True,
        )
        results.append(("webhook_rotate_status", rotate_resp.status_code))
        results.append(("webhook_new_secret", webhook.secret))

        event = WebhookEvent(
            webhook_id=webhook.id,
            status='failed',
            attempts=1,
            payload=json.dumps({'reference': 'UNITTEST-001', 'amount': 100}),
            created_at=datetime.utcnow(),
        )
        db.session.add(event)
        db.session.commit()

        retry_resp = client.post(
            f'/settings/connect/events/{event.id}/retry',
            follow_redirects=True,
        )
        results.append(("event_retry_status", retry_resp.status_code))

        match_resp = client.post(
            f'/settings/connect/events/{event.id}/match',
            data={'match_reference': 'UNITTEST-001'},
            follow_redirects=True,
        )
        results.append(("event_match_status", match_resp.status_code))

        event = WebhookEvent.query.get(event.id)
        results.append(("event_status_after_match", event.status))
        results.append(("event_matched_sale", event.matched_sale_id))

    revoke_session_resp = client.post(
        f'/settings/access/sessions/{active_session.id}/revoke',
        follow_redirects=True,
    )
    results.append(("revoke_session_status", revoke_session_resp.status_code))

print(json.dumps(results, indent=2, default=str))
