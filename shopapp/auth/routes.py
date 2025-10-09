from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import User
from ..utils.otp import request_otp, verify_otp

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user'] = username
            session['role'] = user.role
            session['plan'] = getattr(user, 'plan', None) or current_app.config.get('ACTIVE_PLAN', 'pro')
            if user.role == 'admin':
                session['admin'] = True
            return redirect(url_for('sales.index'))
        flash('Login failed. Check credentials.')
    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()

        if not username or not password or not email:
            flash('Please provide username, password and email.')
            return render_template('auth/register.html')

        user = User(username=username, email=email, phone=phone)
        user.set_password(password)
        try:
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('Username already exists.')
            return render_template('auth/register.html')

        request_otp(username, email)
        flash('Verification code sent to your email.')
        return redirect(url_for('auth.verify_otp_route', username=username, email=email))

    return render_template('auth/register.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp_route():
    username = request.values.get('username', '').strip()
    email = request.values.get('email', '').strip().lower()

    if request.method == 'POST':
        code = request.form['otp'].strip()
        if verify_otp(username, email, code):
            flash('Email verified. You can login now.')
            return redirect(url_for('auth.login'))
        flash('Invalid or expired code.')

    return render_template('auth/verify_otp.html', username=username, email=email)


@auth_bp.route('/request_otp', methods=['POST'])
def request_otp_route():
    username = request.form['username'].strip()
    email = request.form['email'].strip().lower()
    if username and email:
        request_otp(username, email)
        flash('OTP sent to your email.')
    return redirect(url_for('auth.verify_otp_route', username=username, email=email))
