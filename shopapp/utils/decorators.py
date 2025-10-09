from functools import wraps

from flask import redirect, session, url_for


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('auth.login'))
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        role = session.get('role')
        if not (role == 'admin' or session.get('admin') or session.get('is_admin') or session.get('user_is_admin')):
            return redirect(url_for('auth.login'))
        return fn(*args, **kwargs)

    return wrapper
