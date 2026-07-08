import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, redirect, url_for
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from config import Config
from models import db
from models.user import User

from celery import Celery
from flask_migrate import Migrate

# Extensions
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()

# Celery instance placeholder initialized on import
celery = Celery(
    'app',
    broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

def init_celery(celery_app, flask_app):
    celery_app.conf.update(flask_app.config)

    class ContextTask(celery_app.Task):
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery_app.Task = ContextTask

def create_app(config_class=Config):
    global celery
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure required folders exist
    for folder in [app.config['UPLOAD_FOLDER'], app.config['BARCODE_FOLDER'], os.path.join(app.root_path, 'logs')]:
        os.makedirs(folder, exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    # Initialize Celery within application context
    init_celery(celery, app)

    # Automatically create missing database tables on startup
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            app.logger.error(f"Error during db.create_all() on startup: {str(e)}")

    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        from models.user import get_user_by_id
        return get_user_by_id(user_id)

    # Setup Logging
    setup_logging(app)

    # Register blueprints
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.guests import guests_bp
    from routes.upload import upload_bp
    from routes.email import email_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(guests_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(email_bp)

    # Root route
    @app.route('/')
    def index():
        return redirect(url_for('dashboard.index'))

    return app

def setup_logging(app):
    log_dir = os.path.join(app.root_path, 'logs')
    log_file = os.path.join(log_dir, 'app.log')
    
    log_formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    )
    
    # File handler
    file_handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024 * 10, backupCount=5)
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.INFO)
    
    # Configure app logger
    app.logger.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    
    app.logger.info('SNIST Invitation System startup')

# For Gunicorn / WSGI
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
