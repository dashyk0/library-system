from flask import Flask
from config import Config
from blueprints.auth import auth_bp
from blueprints.books import books_bp
from blueprints.reviews import reviews_bp
from blueprints.statistics import stats_bp
import os

app = Flask(__name__)
app.config.from_object(Config)

# Регистрация blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(books_bp)
app.register_blueprint(reviews_bp)
app.register_blueprint(stats_bp)

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)