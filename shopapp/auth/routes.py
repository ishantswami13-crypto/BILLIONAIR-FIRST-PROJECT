from datetime import datetime
import secrets

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..metrics import EVENTS
from ..models import Referral, ShopProfile, User, UserInvite, UserRole, UserSession
from ..security import normalize_role
from ..utils.otp import request_otp, verify_otp
from ..utils.track import track

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            token = secrets.token_hex(32)
            now = datetime.utcnow()
            user.last_login_at = now
            user_session = UserSession(
                user=user,
                session_token=token,
                user_agent=request.headers.get('User-Agent'),
                ip_address=request.remote_addr,
                last_seen_at=now,
            )
            db.session.add(user_session)
            db.session.commit()
            session['user'] = username
            session.permanent = bool(request.form.get('remember_me'))
            role = normalize_role(user.role)
            session['role'] = role
            profile = ShopProfile.query.get(1)
            active_plan = profile.active_plan_slug() if profile else current_app.config.get('ACTIVE_PLAN', 'pro')
            session['plan'] = active_plan
            session['session_token'] = token
            return redirect(url_for('sales.index'))
        flash('Login failed. Check credentials.')
    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    token_value = request.values.get('token', '').strip()
    ref_code = request.values.get('ref', '').strip()

    invite = None
    if token_value:
        invite = UserInvite.query.filter_by(token=token_value).first()
        if not invite or invite.status not in ('pending', 'sent'):
            flash('Invitation link is no longer valid. Ask the owner to resend a new invite.')
            return redirect(url_for('auth.login'))
        if invite.expires_at and invite.expires_at < datetime.utcnow():
            invite.status = 'expired'
            db.session.commit()
            flash('Invitation has expired. Ask the owner to send a new invite.')
            return redirect(url_for('auth.login'))

    referral = None
    if ref_code:
        referral = Referral.query.filter_by(code=ref_code).first()
        if not referral:
            flash('Referral link is no longer valid.', 'warning')
            ref_code = ''

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        token_value = request.form.get('token', '').strip()
        ref_code = request.form.get('ref', '').strip() or ref_code
        referral = Referral.query.filter_by(code=ref_code).first() if ref_code else None

        invite = None
        if token_value:
            invite = UserInvite.query.filter_by(token=token_value).first()
            if not invite or invite.status not in ('pending', 'sent'):
                flash('Invitation link is no longer valid.')
                return redirect(url_for('auth.login'))
            if invite.expires_at and invite.expires_at < datetime.utcnow():
                invite.status = 'expired'
                db.session.commit()
                flash('Invitation has expired. Ask the owner to request a new one.')
                return redirect(url_for('auth.login'))
            email = invite.email.lower()
        else:
            if User.query.count() > 0 and not referral:
                flash('Registration is closed. Ask the shop owner for an invitation link.')
                return redirect(url_for('auth.login'))

        if not username or not password or not email:
            flash('Please provide username, password and email.')
            return render_template('auth/register.html', invite=invite, token=token_value, ref=ref_code)

        user = User(username=username, email=email, phone=phone)
        user.set_password(password)
        if invite and invite.role:
            user.role = invite.role
        else:
            user.role = UserRole.owner
        if invite:
            user.email_verified = True

        try:
            db.session.add(user)
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            flash('Username already exists.')
            return render_template('auth/register.html', invite=invite, token=token_value, ref=ref_code)

        if invite:
            invite.accepted_at = datetime.utcnow()
            invite.status = 'accepted'
            db.session.add(invite)
        if referral:
            referral.invitee_id = user.id
            referral.status = 'ACTIVE'
            db.session.add(referral)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('Could not complete registration. Please try again.')
            return render_template('auth/register.html', invite=invite, token=token_value, ref=ref_code)

        if referral:
            track(EVENTS['REFERRAL_ACTIVATED'], {'code': referral.code}, user_id=referral.inviter_id)

        if invite:
            flash('Account created. You can login now.')
            return redirect(url_for('auth.login'))

        request_otp(username, email)
        flash('Verification code sent to your email.')
        return redirect(url_for('auth.verify_otp_route', username=username, email=email, ref=ref_code))

    return render_template('auth/register.html', invite=invite, token=token_value, ref=ref_code)


@auth_bp.route('/logout')
def logout():
    token = session.get('session_token')
    if token:
        record = UserSession.query.filter_by(session_token=token).first()
        if record and not record.revoked_at:
            record.revoked_at = datetime.utcnow()
            db.session.add(record)
            db.session.commit()
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


@auth_bp.before_app_request
def enforce_active_session():
    if 'user' not in session:
        return
    endpoint = request.endpoint or ''
    if endpoint.startswith('auth.') and endpoint not in {'auth.logout'}:
        return
    token = session.get('session_token')
    if not token:
        session.clear()
        flash('Session expired. Please login again.')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(username=session.get('user')).first()
    if not user:
        session.clear()
        flash('Your account is no longer available. Contact the owner.')
        return redirect(url_for('auth.login'))

    session_record = UserSession.query.filter_by(user_id=user.id, session_token=token).first()
    if not session_record or session_record.revoked_at:
        session.clear()
        flash('You have been signed out from this device.')
        return redirect(url_for('auth.login'))

    now = datetime.utcnow()
    if (now - session_record.last_seen_at).total_seconds() >= 60:
        session_record.last_seen_at = now
        db.session.add(session_record)
        db.session.commit()
    session['role'] = normalize_role(user.role)
    g.user = user
    g.user_id = user.id
    profile = ShopProfile.query.get(1)
    if profile:
        session['plan'] = profile.active_plan_slug()
