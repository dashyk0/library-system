from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, current_app
from utils import get_db_connection
from decorators import login_required, role_required
import csv
from io import StringIO
import datetime

stats_bp = Blueprint('stats', __name__)

def get_journal_entries(page=1, per_page=10):
    conn = get_db_connection()
    if not conn:
        return [], 0
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) as total FROM book_visits")
    total = cursor.fetchone()['total']
    offset = (page - 1) * per_page
    cursor.execute("""
        SELECT bv.id, bv.visit_datetime,
               b.title as book_title,
               u.last_name, u.first_name, u.middle_name
        FROM book_visits bv
        LEFT JOIN books b ON bv.book_id = b.id
        LEFT JOIN users u ON bv.user_id = u.id
        ORDER BY bv.visit_datetime DESC
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    entries = cursor.fetchall()
    for entry in entries:
        if entry['last_name']:
            entry['user_fullname'] = f"{entry['last_name']} {entry['first_name']} {entry['middle_name'] or ''}".strip()
        else:
            entry['user_fullname'] = 'Неаутентифицированный пользователь'
    cursor.close()
    conn.close()
    return entries, total

def get_book_stats(start_date=None, end_date=None, page=1, per_page=10):
    conn = get_db_connection()
    if not conn:
        return [], 0
    cursor = conn.cursor(dictionary=True)
    query_count = """
        SELECT COUNT(DISTINCT b.id) as total
        FROM books b
        JOIN book_visits bv ON b.id = bv.book_id
        WHERE bv.user_id IS NOT NULL
    """
    params = []
    if start_date:
        query_count += " AND DATE(bv.visit_datetime) >= %s"
        params.append(start_date)
    if end_date:
        query_count += " AND DATE(bv.visit_datetime) <= %s"
        params.append(end_date)
    cursor.execute(query_count, params)
    total = cursor.fetchone()['total']
    offset = (page - 1) * per_page
    query_data = """
        SELECT b.id, b.title, COUNT(bv.id) as views_count
        FROM books b
        JOIN book_visits bv ON b.id = bv.book_id
        WHERE bv.user_id IS NOT NULL
    """
    if start_date:
        query_data += " AND DATE(bv.visit_datetime) >= %s"
    if end_date:
        query_data += " AND DATE(bv.visit_datetime) <= %s"
    query_data += " GROUP BY b.id ORDER BY views_count DESC LIMIT %s OFFSET %s"
    params_data = []
    if start_date:
        params_data.append(start_date)
    if end_date:
        params_data.append(end_date)
    params_data.extend([per_page, offset])
    cursor.execute(query_data, params_data)
    stats = cursor.fetchall()
    cursor.close()
    conn.close()
    return stats, total

@stats_bp.route('/statistics')
@login_required
@role_required(['admin'])
def statistics():
    tab = request.args.get('tab', 'journal')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    if tab == 'journal':
        entries, total = get_journal_entries(page, per_page)
        total_pages = (total + per_page - 1) // per_page
        return render_template('statistics.html', tab='journal', entries=entries,
                               page=page, total_pages=total_pages, total=total)
    else:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        stats, total = get_book_stats(start_date, end_date, page, per_page)
        total_pages = (total + per_page - 1) // per_page
        return render_template('statistics.html', tab='stats', stats=stats,
                               page=page, total_pages=total_pages, total=total,
                               start_date=start_date, end_date=end_date)

@stats_bp.route('/statistics/export/journal')
@login_required
@role_required(['admin'])
def export_journal_csv():
    conn = get_db_connection()
    if not conn:
        flash('Ошибка подключения к БД', 'danger')
        return redirect(url_for('stats.statistics', tab='journal'))
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT bv.visit_datetime,
               b.title as book_title,
               u.last_name, u.first_name, u.middle_name
        FROM book_visits bv
        LEFT JOIN books b ON bv.book_id = b.id
        LEFT JOIN users u ON bv.user_id = u.id
        ORDER BY bv.visit_datetime DESC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Дата и время', 'Пользователь', 'Книга'])
    for row in rows:
        user_name = f"{row['last_name']} {row['first_name']} {row['middle_name'] or ''}".strip() if row['last_name'] else 'Неаутентифицированный пользователь'
        writer.writerow([row['visit_datetime'], user_name, row['book_title']])
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=journal_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    response.headers['Content-type'] = 'text/csv'
    return response

@stats_bp.route('/statistics/export/stats')
@login_required
@role_required(['admin'])
def export_stats_csv():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    conn = get_db_connection()
    if not conn:
        flash('Ошибка подключения к БД', 'danger')
        return redirect(url_for('stats.statistics', tab='stats'))
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT b.title, COUNT(bv.id) as views_count
        FROM books b
        JOIN book_visits bv ON b.id = bv.book_id
        WHERE bv.user_id IS NOT NULL
    """
    params = []
    if start_date:
        query += " AND DATE(bv.visit_datetime) >= %s"
        params.append(start_date)
    if end_date:
        query += " AND DATE(bv.visit_datetime) <= %s"
        params.append(end_date)
    query += " GROUP BY b.id ORDER BY views_count DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Название книги', 'Количество просмотров'])
    for row in rows:
        writer.writerow([row['title'], row['views_count']])
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=book_stats_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    response.headers['Content-type'] = 'text/csv'
    return response