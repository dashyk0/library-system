import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'my-secret-key-change-in-production-12345')
    MYSQL_HOST = os.environ.get('MYSQLHOST', 'localhost')
    MYSQL_PORT = int(os.environ.get('MYSQLPORT', 3306))
    MYSQL_USER = os.environ.get('MYSQLUSER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQLPASSWORD', 'root123*')
    #MYSQL_DATABASE = os.environ.get('MYSQLDATABASE', 'library_db')
    MYSQL_DATABASE = os.environ.get('MYSQLDATABASE', 'railway')
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 30
