from functools import wraps
from flask import session, flash, redirect, url_for

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Для выполнения данного действия необходимо пройти процедуру аутентификации', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Необходимо войти в систему', 'warning')
                return redirect(url_for('auth.login'))
            user_role = session.get('role_name')
            if user_role not in allowed_roles:
                flash('У вас недостаточно прав для выполнения данного действия', 'danger')
                return redirect(url_for('books.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator