import mysql.connector
from mysql.connector import Error
import datetime
import hashlib
import os
import bleach
import markdown
from flask import current_app, flash

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=current_app.config['MYSQL_HOST'],
            user=current_app.config['MYSQL_USER'],
            password=current_app.config['MYSQL_PASSWORD'],
            database=current_app.config['MYSQL_DATABASE']
        )
        return conn
    except Error as e:
        print(f"Ошибка подключения: {e}")
        return None

def register_visit(book_id, user_id=None, guest_uuid=None):
    conn = get_db_connection()
    if not conn:
        return
    cursor = conn.cursor()
    today = datetime.date.today()
    if user_id:
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM book_visits 
            WHERE book_id = %s AND user_id = %s AND DATE(visit_datetime) = %s
        """, (book_id, user_id, today))
        cnt = cursor.fetchone()[0]
        if cnt >= 10:
            cursor.close()
            conn.close()
            return
    cursor.execute("""
        INSERT INTO book_visits (book_id, user_id, guest_uuid, visit_datetime)
        VALUES (%s, %s, %s, %s)
    """, (book_id, user_id, guest_uuid, datetime.datetime.now()))
    conn.commit()
    cursor.close()
    conn.close()

def save_cover(file, book_id, conn, cursor):
    """
    Сохраняет обложку, используя уже открытое соединение и курсор (в рамках транзакции).
    Возвращает filename или None.
    """
    if not file or file.filename == '':
        return None
    
    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if ext not in current_app.config['ALLOWED_EXTENSIONS']:
        flash('Недопустимый формат файла. Разрешены: png, jpg, jpeg, gif', 'danger')
        return None
    
    md5_hash = hashlib.md5(file.read()).hexdigest()
    file.seek(0)
    
    # Проверяем существующую обложку (используем переданный курсор)
    try:
        cursor.execute("SELECT id, filename FROM covers WHERE md5_hash = %s", (md5_hash,))
        existing = cursor.fetchone()
        if existing:
            # Обновляем связь с книгой
            cursor.execute("UPDATE covers SET book_id = %s WHERE id = %s", (book_id, existing['id']))
            return existing['filename']
    except Exception as e:
        print(f"Ошибка при проверке обложки: {e}")
        return None
    
    # Сохраняем файл
    filename = f"{md5_hash}.{ext}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    try:
        file.save(filepath)
    except Exception as e:
        print(f"Ошибка при сохранении файла: {e}")
        return None
    
    # Вставляем запись в БД через переданный курсор (в рамках той же транзакции)
    try:
        cursor.execute("""
            INSERT INTO covers (filename, mime_type, md5_hash, book_id)
            VALUES (%s, %s, %s, %s)
        """, (filename, file.mimetype, md5_hash, book_id))
    except Exception as e:
        print("="*50)
        print("ОШИБКА ПРИ ВСТАВКЕ В covers:")
        print(f"filename: {filename}")
        print(f"mime_type: {file.mimetype}")
        print(f"md5_hash: {md5_hash}")
        print(f"book_id: {book_id}")
        print(f"Тип ошибки: {type(e).__name__}")
        print(f"Текст: {str(e)}")
        import traceback
        traceback.print_exc()
        print("="*50)
        if os.path.exists(filepath):
            os.remove(filepath)
        return None
    
    return filename

def get_book_list(page=1, per_page=10):
    conn = get_db_connection()
    if not conn:
        return [], 0
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) as total FROM books")
    total = cursor.fetchone()['total']
    offset = (page - 1) * per_page
    cursor.execute("""
        SELECT id, title, author, year,
               (SELECT AVG(rating) FROM reviews WHERE book_id = books.id) as avg_rating,
               (SELECT COUNT(*) FROM reviews WHERE book_id = books.id) as reviews_count
        FROM books
        ORDER BY year DESC
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    books = cursor.fetchall()
    for book in books:
        cursor.execute("""
            SELECT g.name FROM genres g
            JOIN book_genres bg ON g.id = bg.genre_id
            WHERE bg.book_id = %s
        """, (book['id'],))
        book['genres'] = [g['name'] for g in cursor.fetchall()]
    cursor.close()
    conn.close()
    return books, total

def get_popular_books(limit=5):
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    three_months_ago = datetime.date.today() - datetime.timedelta(days=90)
    cursor.execute("""
        SELECT b.id, b.title, b.author, COUNT(bv.id) as views_count
        FROM books b
        JOIN book_visits bv ON b.id = bv.book_id
        WHERE DATE(bv.visit_datetime) >= %s
        GROUP BY b.id
        ORDER BY views_count DESC
        LIMIT %s
    """, (three_months_ago, limit))
    books = cursor.fetchall()
    cursor.close()
    conn.close()
    return books

def get_recently_viewed(user_id=None, guest_uuid=None, limit=5):
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    if user_id:
        cursor.execute("""
            SELECT b.id, b.title, b.author
            FROM book_visits bv
            JOIN books b ON bv.book_id = b.id
            WHERE bv.user_id = %s
            GROUP BY b.id
            ORDER BY MAX(bv.visit_datetime) DESC
            LIMIT %s
        """, (user_id, limit))
    elif guest_uuid:
        cursor.execute("""
            SELECT b.id, b.title, b.author
            FROM book_visits bv
            JOIN books b ON bv.book_id = b.id
            WHERE bv.guest_uuid = %s
            GROUP BY b.id
            ORDER BY MAX(bv.visit_datetime) DESC
            LIMIT %s
        """, (guest_uuid, limit))
    else:
        cursor.close()
        conn.close()
        return []
    books = cursor.fetchall()
    cursor.close()
    conn.close()
    return books