from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from utils import get_db_connection

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login = request.form['login']
        password = request.form['password']
        remember = 'remember' in request.form
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT u.id, u.login, u.password_hash, u.last_name, u.first_name, u.middle_name, r.name as role_name
                FROM users u
                JOIN roles r ON u.role_id = r.id
                WHERE u.login = %s
            """, (login,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            if user and check_password_hash(user['password_hash'], password):
                session.clear()
                session['user_id'] = user['id']
                session['user_name'] = f"{user['last_name']} {user['first_name']} {user['middle_name'] or ''}".strip()
                session['role_name'] = user['role_name']
                session.permanent = remember
                flash('Вы успешно вошли в систему', 'success')
                return redirect(url_for('books.index'))
            else:
                flash('Невозможно аутентифицироваться с указанными логином и паролем', 'danger')
        else:
            flash('Ошибка подключения к базе данных', 'danger')
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('books.index'))