from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Tuple

from sqlalchemy import func

from ..extensions import db
from ..models import Customer, Expense, ExpenseCategory, Sale, Item


@dataclass
class DailyRow:
    date: datetime
    revenue: float
    expenses: float
    profit: float
    discount: float
    tax: float


def _collect_sales(start: datetime) -> List[Sale]:
    return (
        Sale.query
        .filter(Sale.date >= start)
        .order_by(Sale.date.asc())
        .all()
    )


def _collect_expenses(start: datetime) -> List[Expense]:
    return (
        Expense.query
        .filter(Expense.date >= start.date())
        .order_by(Expense.date.asc())
        .all()
    )


def _aggregate_daily(sales: Iterable[Sale], expenses: Iterable[Expense]) -> Dict[datetime, DailyRow]:
    rows: Dict[datetime, DailyRow] = {}
    expense_map: Dict[datetime, float] = defaultdict(float)
    for exp in expenses:
        expense_map[exp.date] += float(exp.amount or 0)

    for sale in sales:
        day = sale.date.date()
        if day not in rows:
            rows[day] = DailyRow(
                date=datetime.combine(day, datetime.min.time()),
                revenue=0.0,
                expenses=0.0,
                profit=0.0,
                discount=0.0,
                tax=0.0,
            )
        row = rows[day]
        row.revenue += float(sale.net_total or 0)
        row.discount += float(sale.discount or 0)
        row.tax += float(sale.tax or 0)

    for day, amount in expense_map.items():
        d = datetime.combine(day, datetime.min.time())
        if day not in rows:
            rows[day] = DailyRow(
                date=d,
                revenue=0.0,
                expenses=float(amount),
                profit=-float(amount),
                discount=0.0,
                tax=0.0,
            )
        else:
            rows[day].expenses += float(amount)

    for row in rows.values():
        row.profit = row.revenue - row.expenses

    return rows


def _group_period(rows: Iterable[DailyRow], period: str) -> List[Dict[str, object]]:
    buckets: Dict[str, Dict[str, float]] = defaultdict(lambda: {"revenue": 0.0, "expenses": 0.0, "profit": 0.0})

    for row in rows:
        if period == "weekly":
            iso_year, iso_week, _ = row.date.isocalendar()
            key = f"{iso_year}-W{iso_week:02d}"
        elif period == "monthly":
            key = row.date.strftime("%Y-%m")
        else:
            key = row.date.strftime("%Y-%m-%d")

        bucket = buckets[key]
        bucket["revenue"] += row.revenue
        bucket["expenses"] += row.expenses
        bucket["profit"] += row.profit

    ordered = []
    for key in sorted(buckets.keys()):
        bucket = buckets[key]
        ordered.append({
            "label": key,
            "revenue": round(bucket["revenue"], 2),
            "expenses": round(bucket["expenses"], 2),
            "profit": round(bucket["profit"], 2),
        })
    return ordered


def _build_heatmap(sales: Iterable[Sale]) -> Dict[str, object]:
    matrix = [[0.0 for _ in range(24)] for _ in range(7)]
    max_value = 0.0
    for sale in sales:
        dow = sale.date.weekday()  # Monday=0
        hour = sale.date.hour
        matrix[dow][hour] += float(sale.net_total or 0)
        if matrix[dow][hour] > max_value:
            max_value = matrix[dow][hour]

    return {
        "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "hours": list(range(24)),
        "matrix": matrix,
        "max": max_value,
    }


def _ltv_leaderboard(limit: int = 10) -> List[Dict[str, object]]:
    rows = (
        db.session.query(
            Sale.customer_id,
            func.coalesce(func.sum(Sale.net_total), 0),
            func.count(Sale.id),
            func.max(Sale.date),
        )
        .filter(Sale.customer_id.isnot(None))
        .group_by(Sale.customer_id)
        .order_by(func.sum(Sale.net_total).desc())
        .limit(limit)
        .all()
    )
    customer_ids = [row[0] for row in rows if row[0]]
    customers = {c.id: c for c in Customer.query.filter(Customer.id.in_(customer_ids)).all()}

    leaderboard = []
    for customer_id, total, orders, last_date in rows:
        customer = customers.get(customer_id)
        leaderboard.append({
            "customer": customer.name if customer else f"Customer #{customer_id}",
            "email": customer.email if customer else None,
            "total": float(total or 0),
            "orders": int(orders or 0),
            "last_purchase": last_date.strftime("%Y-%m-%d %H:%M") if last_date else None,
        })
    return leaderboard


def _category_breakdown(start: datetime) -> List[Dict[str, object]]:
    label_expr = func.coalesce(ExpenseCategory.name, Expense.category, 'Uncategorised')

    rows = (
        db.session.query(
            label_expr.label('label'),
            func.coalesce(func.sum(Expense.amount), 0).label('total'),
            ExpenseCategory.color,
        )
        .outerjoin(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
        .filter(Expense.date >= start.date())
        .group_by(label_expr, ExpenseCategory.color)
        .order_by(func.sum(Expense.amount).desc())
        .all()
    )

    total = sum(float(row.total or 0) for row in rows)
    breakdown = []
    for label, total_amount, color in rows:
        amount = float(total_amount or 0)
        share = (amount / total * 100) if total else 0
        breakdown.append({
            "name": label or 'Uncategorised',
            "amount": round(amount, 2),
            "color": color or '#62b5ff',
            "share": round(share, 1),
        })
    return breakdown


def _item_metrics(items: Iterable[Item], sales: Iterable[Sale]) -> Dict[str, Dict[str, object]]:
    metrics: Dict[str, Dict[str, object]] = {}
    for item in items:
        metrics[item.name.lower()] = {
            "item": item,
            "units_sold": 0,
            "revenue": 0.0,
            "last_sale": None,
            "sale_count": 0,
        }

    for sale in sales:
        key = (sale.item or '').lower()
        if key not in metrics:
            continue
        entry = metrics[key]
        entry["units_sold"] += int(sale.quantity or 0)
        entry["revenue"] += float(sale.net_total or 0)
        entry["sale_count"] += 1
        if entry["last_sale"] is None or sale.date > entry["last_sale"]:
            entry["last_sale"] = sale.date

    return metrics


def _recommendations(items: Iterable[Item], item_metrics: Dict[str, Dict[str, object]]) -> List[Dict[str, str]]:
    recs: List[Dict[str, str]] = []
    now = datetime.utcnow()

    for item in items:
        key = item.name.lower()
        data = item_metrics.get(key, {"units_sold": 0, "revenue": 0.0, "last_sale": None, "sale_count": 0})
        reorder_level = item.reorder_level if item.reorder_level is not None else 5
        stock = item.current_stock or 0

        if stock <= reorder_level:
            recs.append({
                "type": "reorder",
                "title": f"Reorder {item.name}",
                "message": f"{stock} left in stock (reorder at {reorder_level}). Place a purchase order soon.",
            })

        last_sale = data.get("last_sale")
        days_since = (now - last_sale).days if last_sale else None
        if stock > reorder_level and (data.get("units_sold", 0) == 0 or (days_since and days_since > 30)):
            reason = "No sales recorded yet" if data.get("units_sold", 0) == 0 else f"Last sold {days_since} days ago"
            recs.append({
                "type": "slow",
                "title": f"Review pricing for {item.name}",
                "message": f"{reason}. Consider promotions, bundling, or adjusting reorder level.",
            })

        if data.get("units_sold", 0) >= max(10, reorder_level * 2) and stock <= reorder_level * 2:
            recs.append({
                "type": "fast",
                "title": f"High demand for {item.name}",
                "message": f"{data['units_sold']} units sold recently. Stock at {stock}; plan replenishment to avoid stock-outs.",
            })

    if not recs:
        recs.append({
            "type": "info",
            "title": "All clear",
            "message": "Inventory levels look balanced. Keep monitoring analytics for new opportunities.",
        })

    return recs


def load_analytics(days: int = 90) -> Dict[str, object]:
    start = datetime.utcnow() - timedelta(days=days)
    sales = _collect_sales(start)
    expenses = _collect_expenses(start)
    items = Item.query.order_by(Item.name.asc()).all()
    item_metrics = _item_metrics(items, sales)
    daily_rows_map = _aggregate_daily(sales, expenses)
    daily_rows = [daily_rows_map[day] for day in sorted(daily_rows_map.keys())]

    summary = {
        "total_revenue": round(sum(row.revenue for row in daily_rows), 2),
        "total_expenses": round(sum(row.expenses for row in daily_rows), 2),
        "total_profit": round(sum(row.profit for row in daily_rows), 2),
        "average_daily_profit": round(sum(row.profit for row in daily_rows) / len(daily_rows), 2) if daily_rows else 0,
    }

    recent_sales = [sale for sale in sales if sale.date >= datetime.utcnow() - timedelta(days=30)]
    heatmap = _build_heatmap(recent_sales)

    daily_series = [{
        "label": row.date.strftime("%Y-%m-%d"),
        "revenue": round(row.revenue, 2),
        "expenses": round(row.expenses, 2),
        "profit": round(row.profit, 2),
    } for row in daily_rows]

    weekly_series = _group_period(daily_rows, "weekly")
    monthly_series = _group_period(daily_rows, "monthly")

    return {
        "summary": summary,
        "daily": daily_series,
        "weekly": weekly_series,
        "monthly": monthly_series,
        "heatmap": heatmap,
        "ltv": _ltv_leaderboard(),
        "categories": _category_breakdown(start),
        "recommendations": _recommendations(items, item_metrics),
    }


def build_daily_csv(data: List[Dict[str, object]]) -> List[List[str]]:
    rows = [["Date", "Revenue", "Expenses", "Profit"]]
    for entry in data:
        rows.append([
            entry["label"],
            f"{entry['revenue']:.2f}",
            f"{entry['expenses']:.2f}",
            f"{entry['profit']:.2f}",
        ])
    return rows
