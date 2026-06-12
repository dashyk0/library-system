from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from utils import get_db_connection
from decorators import login_required
import bleach

reviews_bp = Blueprint('reviews', __name__)

@reviews_bp.route('/book/<int:book_id>/review/add', methods=['GET', 'POST'])
@login_required
def add_review(book_id):
    conn = get_db_connection()
    if not conn:
        flash('Ошибка подключения к БД', 'danger')
        return redirect(url_for('books.book_detail', book_id=book_id))
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, title FROM books WHERE id = %s", (book_id,))
    book = cursor.fetchone()
    if not book:
        flash('Книга не найдена', 'warning')
        return redirect(url_for('books.index'))
    cursor.execute("SELECT id FROM reviews WHERE book_id = %s AND user_id = %s", (book_id, session['user_id']))
    if cursor.fetchone():
        flash('Вы уже оставили рецензию на эту книгу', 'warning')
        cursor.close()
        conn.close()
        return redirect(url_for('books.book_detail', book_id=book_id))
    if request.method == 'POST':
        rating = request.form.get('rating', type=int)
        text = request.form.get('text', '').strip()
        if rating is None or rating < 0 or rating > 5:
            flash('Оценка должна быть от 0 до 5', 'danger')
            return render_template('review_form.html', book=book, rating=rating, text=text)
        if not text:
            flash('Текст рецензии не может быть пустым', 'danger')
            return render_template('review_form.html', book=book, rating=rating, text=text)
        clean_text = bleach.clean(text, tags=[], attributes={}, strip=True)
        try:
            cursor.execute("""
                INSERT INTO reviews (book_id, user_id, rating, text, created_at)
                VALUES (%s, %s, %s, %s, NOW())
            """, (book_id, session['user_id'], rating, clean_text))
            conn.commit()
            flash('Рецензия успешно добавлена', 'success')
            return redirect(url_for('books.book_detail', book_id=book_id))
        except Exception as e:
            conn.rollback()
            flash(f'Ошибка при сохранении рецензии: {str(e)}', 'danger')
            return render_template('review_form.html', book=book, rating=rating, text=text)
        finally:
            cursor.close()
            conn.close()
    cursor.close()
    conn.close()
    return render_template('review_form.html', book=book, rating=5, text='')