from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from utils import get_db_connection, get_book_list, get_popular_books, get_recently_viewed, register_visit, save_cover
from decorators import login_required, role_required
import uuid
import bleach
import markdown
import os

books_bp = Blueprint('books', __name__)

ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'a', 'img']
ALLOWED_ATTRIBUTES = {'a': ['href', 'title'], 'img': ['src', 'alt', 'title']}

@books_bp.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    books, total = get_book_list(page, per_page)
    total_pages = (total + per_page - 1) // per_page
    popular_books = get_popular_books(5)
    user_id = session.get('user_id')
    guest_uuid = session.get('guest_uuid')
    if not guest_uuid and not user_id:
        guest_uuid = str(uuid.uuid4())
        session['guest_uuid'] = guest_uuid
    recently_viewed = get_recently_viewed(user_id, guest_uuid, 5)
    return render_template('index.html', books=books, page=page, total_pages=total_pages, total=total,
                           popular_books=popular_books, recently_viewed=recently_viewed)

@books_bp.route('/book/<int:book_id>')
def book_detail(book_id):
    conn = get_db_connection()
    if not conn:
        flash('Ошибка подключения к БД', 'danger')
        return redirect(url_for('books.index'))
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT b.*, c.filename as cover_filename, c.mime_type
        FROM books b
        LEFT JOIN covers c ON b.id = c.book_id
        WHERE b.id = %s
    """, (book_id,))
    book = cursor.fetchone()
    if not book:
        flash('Книга не найдена', 'warning')
        return redirect(url_for('books.index'))
    book['description_html'] = bleach.clean(
        markdown.markdown(book['description'], extensions=['extra']),
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES
    )
    cursor.execute("""
        SELECT g.id, g.name FROM genres g
        JOIN book_genres bg ON g.id = bg.genre_id
        WHERE bg.book_id = %s
    """, (book_id,))
    book['genres'] = cursor.fetchall()
    cursor.execute("""
        SELECT r.*, u.last_name, u.first_name, u.middle_name
        FROM reviews r
        JOIN users u ON r.user_id = u.id
        WHERE r.book_id = %s
        ORDER BY r.created_at DESC
    """, (book_id,))
    reviews = cursor.fetchall()
    for rev in reviews:
        rev['text_html'] = bleach.clean(
            markdown.markdown(rev['text'], extensions=['extra']),
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES
        )
        rev['user_fullname'] = f"{rev['last_name']} {rev['first_name']} {rev['middle_name'] or ''}".strip()
    can_review = False
    user_review = None
    if 'user_id' in session:
        cursor.execute("SELECT id FROM reviews WHERE book_id = %s AND user_id = %s", (book_id, session['user_id']))
        if cursor.fetchone() is None:
            can_review = True
        else:
            cursor.execute("SELECT * FROM reviews WHERE book_id = %s AND user_id = %s", (book_id, session['user_id']))
            user_review = cursor.fetchone()
            if user_review:
                user_review['text_html'] = bleach.clean(
                    markdown.markdown(user_review['text'], extensions=['extra']),
                    tags=ALLOWED_TAGS,
                    attributes=ALLOWED_ATTRIBUTES
                )
    cursor.close()
    conn.close()
    user_id = session.get('user_id')
    guest_uuid = session.get('guest_uuid')
    if not guest_uuid and not user_id:
        guest_uuid = str(uuid.uuid4())
        session['guest_uuid'] = guest_uuid
    register_visit(book_id, user_id, guest_uuid)
    return render_template('book_detail.html', book=book, reviews=reviews, can_review=can_review, user_review=user_review)

@books_bp.route('/book/add', methods=['GET', 'POST'])
@login_required
@role_required(['admin'])
def add_book():
    conn = get_db_connection()
    if not conn:
        flash('Ошибка подключения к БД', 'danger')
        return redirect(url_for('books.index'))
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM genres ORDER BY name")
    all_genres = cursor.fetchall()
    cursor.close()
    conn.close()

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        year = request.form['year']
        publisher = request.form['publisher']
        author = request.form['author']
        pages = request.form['pages']
        genre_ids = request.form.getlist('genres')
        cover_file = request.files.get('cover')

        # Санитайзер описания книги
        description = bleach.clean(description, tags=[], attributes={}, strip=True)

        if not all([title, description, year, publisher, author, pages]):
            flash('Все поля обязательны для заполнения', 'danger')
            return render_template('book_form.html', book=None, genres=all_genres, selected_genres=[])

        try:
            pages = int(pages)
            year = int(year)
        except ValueError:
            flash('Год и объём должны быть числами', 'danger')
            return render_template('book_form.html', book=None, genres=all_genres, selected_genres=[])

        conn = get_db_connection()
        if not conn:
            flash('Ошибка подключения к БД', 'danger')
            return render_template('book_form.html', book=None, genres=all_genres, selected_genres=[])

        try:
            cursor = conn.cursor()
            conn.start_transaction()

            # 1. Вставляем книгу
            cursor.execute("""
                INSERT INTO books (title, description, year, publisher, author, pages)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (title, description, year, publisher, author, pages))
            book_id = cursor.lastrowid

            # 2. Жанры
            for gid in genre_ids:
                cursor.execute("INSERT INTO book_genres (book_id, genre_id) VALUES (%s, %s)", (book_id, gid))

            # 3. Обложка (передаём conn и cursor)
            if cover_file and cover_file.filename != '':
                filename = save_cover(cover_file, book_id, conn, cursor)
                if not filename:
                    raise Exception("Не удалось сохранить обложку")

            conn.commit()
            flash('Книга успешно добавлена', 'success')
            return redirect(url_for('books.book_detail', book_id=book_id))

        except Exception as e:
            conn.rollback()
            flash(f'При сохранении данных возникла ошибка. Проверьте корректность введённых данных. ({str(e)})', 'danger')
            return render_template('book_form.html', book=None, genres=all_genres, selected_genres=genre_ids)

        finally:
            cursor.close()
            conn.close()

    return render_template('book_form.html', book=None, genres=all_genres, selected_genres=[])
@books_bp.route('/book/edit/<int:book_id>', methods=['GET', 'POST'])
@login_required
@role_required(['admin', 'moderator'])
def edit_book(book_id):
    conn = get_db_connection()
    if not conn:
        flash('Ошибка подключения к БД', 'danger')
        return redirect(url_for('books.index'))
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM books WHERE id = %s", (book_id,))
    book = cursor.fetchone()
    if not book:
        flash('Книга не найдена', 'warning')
        return redirect(url_for('books.index'))
    cursor.execute("SELECT genre_id FROM book_genres WHERE book_id = %s", (book_id,))
    current_genre_ids = [str(row['genre_id']) for row in cursor.fetchall()]
    cursor.execute("SELECT id, name FROM genres ORDER BY name")
    all_genres = cursor.fetchall()
    cursor.close()
    conn.close()

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        year = request.form['year']
        publisher = request.form['publisher']
        author = request.form['author']
        pages = request.form['pages']
        genre_ids = request.form.getlist('genres')

        # Санитайзер описания книги
        description = bleach.clean(description, tags=[], attributes={}, strip=True)

        if not all([title, description, year, publisher, author, pages]):
            flash('Все поля обязательны для заполнения', 'danger')
            return render_template('book_form.html', book=book, genres=all_genres, selected_genres=current_genre_ids)

        try:
            pages = int(pages)
            year = int(year)
        except ValueError:
            flash('Год и объём должны быть числами', 'danger')
            return render_template('book_form.html', book=book, genres=all_genres, selected_genres=current_genre_ids)

        conn = get_db_connection()
        if not conn:
            flash('Ошибка подключения к БД', 'danger')
            return render_template('book_form.html', book=book, genres=all_genres, selected_genres=current_genre_ids)

        try:
            cursor = conn.cursor()
            conn.start_transaction()
            cursor.execute("""
                UPDATE books SET title=%s, description=%s, year=%s, publisher=%s, author=%s, pages=%s
                WHERE id=%s
            """, (title, description, year, publisher, author, pages, book_id))
            cursor.execute("DELETE FROM book_genres WHERE book_id = %s", (book_id,))
            for gid in genre_ids:
                cursor.execute("INSERT INTO book_genres (book_id, genre_id) VALUES (%s, %s)", (book_id, gid))
            conn.commit()
            flash('Книга успешно обновлена', 'success')
            return redirect(url_for('books.book_detail', book_id=book_id))
        except Exception as e:
            conn.rollback()
            flash(f'При сохранении данных возникла ошибка. Проверьте корректность введённых данных. ({str(e)})', 'danger')
            return render_template('book_form.html', book=book, genres=all_genres, selected_genres=genre_ids)
        finally:
            cursor.close()
            conn.close()

    # Для отображения обложки в форме редактирования
    conn2 = get_db_connection()
    if conn2:
        cur2 = conn2.cursor(dictionary=True)
        cur2.execute("SELECT filename FROM covers WHERE book_id = %s", (book_id,))
        cover = cur2.fetchone()
        if cover:
            book['cover_filename'] = cover['filename']
        cur2.close()
        conn2.close()
    return render_template('book_form.html', book=book, genres=all_genres, selected_genres=current_genre_ids)

@books_bp.route('/book/delete/<int:book_id>')
@login_required
@role_required(['admin'])
def delete_book(book_id):
    conn = get_db_connection()
    if not conn:
        flash('Ошибка подключения к БД', 'danger')
        return redirect(url_for('books.index'))
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT filename FROM covers WHERE book_id = %s", (book_id,))
    cover = cursor.fetchone()
    cursor.execute("DELETE FROM books WHERE id = %s", (book_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    cursor.close()
    conn.close()
    if deleted:
        if cover and cover['filename']:
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], cover['filename'])
            if os.path.exists(filepath):
                os.remove(filepath)
        flash('Книга успешно удалена', 'success')
    else:
        flash('Книга не найдена', 'danger')
    return redirect(url_for('books.index'))