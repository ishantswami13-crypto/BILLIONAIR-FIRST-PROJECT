from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import func

from ..extensions import db
from ..models import Expense, ExpenseCategory
from ..utils.decorators import login_required

expenses_bp = Blueprint('expenses', __name__)


def _load_categories():
    return ExpenseCategory.query.order_by(ExpenseCategory.name.asc()).all()


def _suggest_category(text: str, categories) -> ExpenseCategory | None:
    haystack = (text or '').lower()
    if not haystack:
        return None
    for category in categories:
        if not category.keywords:
            continue
        for raw_keyword in category.keywords.split(','):
            keyword = raw_keyword.strip().lower()
            if keyword and keyword in haystack:
                return category
    return None



@expenses_bp.route('/expenses', methods=['GET', 'POST'])
@login_required
def expenses():
    categories = _load_categories()
    if request.method == 'POST':
        entry_date = request.form.get('date') or date.today().isoformat()
        category_id_raw = request.form.get('category_id') or ''
        free_category = (request.form.get('category') or '').strip()
        amount = float(request.form['amount'])
        notes = request.form.get('notes', '')

        category_obj = None
        if category_id_raw:
            category_obj = ExpenseCategory.query.get(int(category_id_raw))
        if not category_obj and free_category:
            category_obj = ExpenseCategory.query.filter(
                func.lower(ExpenseCategory.name) == free_category.lower()
            ).first()
        if not category_obj:
            suggestion = _suggest_category(f"{free_category} {notes}", categories)
            if suggestion:
                category_obj = suggestion

        category_label = (category_obj.name if category_obj else free_category) or 'Uncategorised'

        db.session.add(Expense(
            date=entry_date,
            category=category_label,
            category_id=category_obj.id if category_obj else None,
            amount=amount,
            notes=notes
        ))
        db.session.commit()
        flash(f'Expense recorded under {category_label}.', 'success')
        return redirect(url_for('expenses.expenses'))

    rows = Expense.query.order_by(Expense.date.desc()).all()
    return render_template('expenses/list.html', expenses=rows, categories=categories)


@expenses_bp.route('/expenses/categories', methods=['GET', 'POST'])
@login_required
def categories():
    categories = _load_categories()
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        color = request.form.get('color') or '#62b5ff'
        keywords = (request.form.get('keywords') or '').strip()

        if not name:
            flash('Category name is required.', 'danger')
            return redirect(url_for('expenses.categories'))

        existing = ExpenseCategory.query.filter(func.lower(ExpenseCategory.name) == name.lower()).first()
        if existing:
            flash('Category already exists.', 'warning')
            return redirect(url_for('expenses.categories'))

        db.session.add(ExpenseCategory(name=name, color=color, keywords=keywords))
        db.session.commit()
        flash('Category created.', 'success')
        return redirect(url_for('expenses.categories'))

    return render_template('expenses/categories.html', categories=categories)


@expenses_bp.route('/expenses/categories/<int:category_id>/update', methods=['POST'])
@login_required
def update_category(category_id: int):
    category = ExpenseCategory.query.get_or_404(category_id)
    category.name = (request.form.get('name') or category.name).strip() or category.name
    category.color = request.form.get('color') or category.color
    category.keywords = (request.form.get('keywords') or '').strip()
    db.session.commit()
    flash('Category updated.', 'success')
    return redirect(url_for('expenses.categories'))


@expenses_bp.route('/expenses/categories/<int:category_id>/delete', methods=['POST'])
@login_required
def delete_category(category_id: int):
    category = ExpenseCategory.query.get_or_404(category_id)
    Expense.query.filter_by(category_id=category.id).update({
        'category_id': None,
        'category': category.name  # preserve label
    })
    db.session.delete(category)
    db.session.commit()
    flash('Category deleted. Existing expenses remain tagged with the last known name.', 'info')
    return redirect(url_for('expenses.categories'))
