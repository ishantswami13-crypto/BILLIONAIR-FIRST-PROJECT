from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import func

from ..extensions import db
from ..models import Expense, ExpenseCategory
from ..utils.audit import log_event
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
    suggestions = {}
    for expense in rows:
        if expense.category_id:
            continue
        suggestion = _suggest_category(f"{expense.category or ''} {expense.notes or ''}", categories)
        if suggestion:
            suggestions[expense.id] = suggestion
    return render_template('expenses/list.html', expenses=rows, categories=categories, suggestions=suggestions)


@expenses_bp.route('/expenses/reassign', methods=['POST'])
@login_required
def bulk_reassign():
    expense_ids = [int(x) for x in request.form.getlist('expense_ids') if x.isdigit()]
    if not expense_ids:
        flash('Select at least one expense to reassign.', 'warning')
        return redirect(url_for('expenses.expenses'))

    category_id_raw = request.form.get('bulk_category_id') or ''
    custom_label = (request.form.get('bulk_category') or '').strip()

    category = None
    if category_id_raw:
        category = ExpenseCategory.query.get(int(category_id_raw))

    if not category and not custom_label:
        flash('Choose a target category or supply a custom label.', 'warning')
        return redirect(url_for('expenses.expenses'))

    label = category.name if category else custom_label

    updated = 0
    for expense in Expense.query.filter(Expense.id.in_(expense_ids)).all():
        expense.category_id = category.id if category else None
        expense.category = label
        updated += 1

    if updated:
        db.session.commit()
        log_event(
            'expenses_bulk_reassign',
            resource_type='expense',
            resource_id=None,
            after={'count': updated, 'category': label},
        )
        flash(f'Updated {updated} expenses to {label}.', 'success')
    else:
        flash('No expenses updated.', 'info')
    return redirect(url_for('expenses.expenses'))


@expenses_bp.route('/expenses/<int:expense_id>/apply-suggestion', methods=['POST'])
@login_required
def apply_suggestion(expense_id: int):
    expense = Expense.query.get_or_404(expense_id)
    categories = _load_categories()
    suggestion = _suggest_category(f"{expense.category or ''} {expense.notes or ''}", categories)
    if not suggestion:
        flash('No suggestion available for this expense.', 'warning')
        return redirect(url_for('expenses.expenses'))

    expense.category_id = suggestion.id
    expense.category = suggestion.name
    db.session.commit()
    log_event(
        'expense_apply_suggestion',
        resource_type='expense',
        resource_id=expense.id,
        after={'category': suggestion.name},
    )
    flash(f'Applied suggested category: {suggestion.name}.', 'success')
    return redirect(url_for('expenses.expenses'))


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
