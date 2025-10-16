from datetime import datetime, timedelta
import csv
import io

from flask import Blueprint, make_response, render_template, request, send_file, jsonify
from sqlalchemy import func

from ..extensions import db
from ..models import Credit, Expense, Sale
from ..utils.analytics import build_daily_csv, load_analytics
from ..utils.decorators import login_required
from ..utils.pdfs import create_zreport_pdf

reports_bp = Blueprint('reports', __name__)


def day_bounds(target: datetime) -> tuple[datetime, datetime]:
    start = datetime(target.year, target.month, target.day)
    end = start + timedelta(days=1) - timedelta(seconds=1)
    return start, end


def build_summary(date_str: str | None):
    if date_str:
        try:
            target_day = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            target_day = datetime.utcnow()
    else:
        target_day = datetime.utcnow()
    start, end = day_bounds(target_day)

    totals = (db.session.query(
        func.coalesce(func.sum(Sale.net_total), 0),
        func.coalesce(func.sum(Sale.discount), 0),
        func.coalesce(func.sum(Sale.tax), 0),
        func.count(Sale.id),
        func.coalesce(func.min(Sale.date), None),
        func.coalesce(func.max(Sale.date), None)
    ).filter(Sale.date.between(start, end)).first())

    payment_rows = (
        db.session.query(Sale.payment_method,
                         func.count(Sale.id),
                         func.coalesce(func.sum(Sale.net_total), 0))
        .filter(Sale.date.between(start, end))
        .group_by(Sale.payment_method)
        .all()
    )
    payment_breakdown = [
        {
            'method': method or 'cash',
            'transactions': int(tx or 0),
            'amount': float(amount or 0)
        }
        for method, tx, amount in payment_rows
    ]
    payment_total = sum(row['amount'] for row in payment_breakdown)

    top_items = (
        db.session.query(
            Sale.item,
            func.coalesce(func.sum(Sale.quantity), 0),
            func.coalesce(func.sum(Sale.net_total), 0)
        )
        .filter(Sale.date.between(start, end))
        .group_by(Sale.item)
        .order_by(func.sum(Sale.net_total).desc())
        .limit(5)
        .all()
    )
    top_items = [
        {'item': row[0], 'quantity': int(row[1] or 0), 'amount': float(row[2] or 0)}
        for row in top_items
    ]

    udhar_row = (db.session.query(func.count(Sale.id), func.coalesce(func.sum(Sale.net_total), 0))
                 .filter(Sale.date.between(start, end))
                 .filter(func.coalesce(Sale.payment_method, 'cash') == 'udhar')
                 .first() or (0, 0))

    outstanding_row = (
        db.session.query(func.coalesce(func.sum(Credit.total), 0), func.count(Credit.id))
        .filter(Credit.status.in_(['unpaid', 'adjusted']))
        .first() or (0, 0)
    )

    returns_total = 0.0

    expenses_total = (
        db.session.query(func.coalesce(func.sum(Expense.amount), 0))
        .filter(Expense.date == target_day.date())
        .scalar() or 0
    )

    summary = {
        'date': target_day.date().isoformat(),
        'display_date': target_day.strftime('%d %b %Y'),
        'totals': {
            'revenue': float(totals[0] or 0),
            'discount': float(totals[1] or 0),
            'tax': float(totals[2] or 0),
            'transactions': int(totals[3] or 0),
            'average_bill': round((totals[0] / totals[3]), 2) if totals[3] else 0,
            'unique_customers': 0,
            'first_sale': totals[4],
            'last_sale': totals[5]
        },
        'payment_breakdown': payment_breakdown,
        'payment_total': payment_total,
        'dominant_method': payment_breakdown[0]['method'] if payment_breakdown else None,
        'top_items': top_items,
        'udhar': {
            'count': int(udhar_row[0] or 0),
            'amount': float(udhar_row[1] or 0),
            'outstanding_total': float(outstanding_row[0] or 0),
            'outstanding_accounts': int(outstanding_row[1] or 0)
        },
        'returns_total': returns_total,
        'expenses_total': float(expenses_total or 0),
        'net_after_expenses': float((totals[0] or 0) - (expenses_total or 0)),
        'peak_hour': None,
        'peak_hour_amount': 0
    }
    return summary


@reports_bp.route('/zreport')
@login_required
def zreport_view():
    summary = build_summary(request.args.get('date'))
    return render_template('reports/zreport.html', report=summary)


@reports_bp.route('/zreport/pdf')
@login_required
def zreport_pdf():
    summary = build_summary(request.args.get('date'))
    path = create_zreport_pdf(summary)
    return send_file(
        path,
        as_attachment=True,
        download_name=f"zreport_{summary['date']}.pdf",
        mimetype='application/pdf'
    )


def _resolve_days() -> int:
    try:
        days = int(request.args.get('days', 90))
    except (TypeError, ValueError):
        days = 90
    return max(7, min(days, 365))


@reports_bp.route('/analytics')
@login_required
def analytics_view():
    days = _resolve_days()
    analytics = load_analytics(days=days)
    return render_template('reports/analytics.html', analytics=analytics, days=days)


@reports_bp.route('/analytics/export.csv')
@login_required
def analytics_export():
    days = _resolve_days()
    analytics = load_analytics(days=days)
    csv_rows = build_daily_csv(analytics['daily'])

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerows(csv_rows)

    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=analytics_{days}d.csv'
    return response


@reports_bp.route('/analytics/data')
@login_required
def analytics_data():
    days = _resolve_days()
    analytics = load_analytics(days=days)
    return jsonify({
        'days': days,
        'analytics': analytics,
    })
