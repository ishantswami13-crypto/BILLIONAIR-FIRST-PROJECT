from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Expense
from ..utils.decorators import login_required

expenses_bp = Blueprint('expenses', __name__)


@expenses_bp.route('/expenses', methods=['GET', 'POST'])
@login_required
def expenses():
    if request.method == 'POST':
        entry_date = request.form.get('date') or date.today().isoformat()
        category = request.form['category']
        amount = float(request.form['amount'])
        notes = request.form.get('notes', '')
        db.session.add(Expense(date=entry_date, category=category, amount=amount, notes=notes))
        db.session.commit()
        flash('Expense recorded.')
        return redirect(url_for('expenses.expenses'))

    rows = Expense.query.order_by(Expense.date.desc()).all()
    return render_template('expenses/list.html', expenses=rows)
