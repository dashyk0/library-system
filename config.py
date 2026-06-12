import os

class Config:
    SECRET_KEY = 'my-secret-key-change-in-production-12345'  
    MYSQL_HOST = 'localhost'
    MYSQL_USER = 'root'          
    MYSQL_PASSWORD = 'root123*'   # пароль root MySQL
    MYSQL_DATABASE = 'library_db'
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 30  # 30 дней для "запомнить меня"
