from functools import wraps

from flask import redirect, session


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect('/login')
        return fn(*args, **kwargs)

    return wrapper
