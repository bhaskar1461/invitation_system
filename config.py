import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'snist-default-development-secret-key-987654321')
    DEBUG = os.environ.get('FLASK_ENV') == 'development'

    # Database settings
    # Default to SQLite if DATABASE_URL is not set
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///guest_invitation.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload configurations
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB
    ALLOWED_EXTENSIONS = {'xlsx'}

    # Barcode path (located inside static/barcodes for easy web serving)
    BARCODE_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static', 'barcodes')

    # Mail configurations (SMTP protocol matching helpdesk)
    SMTP_HOST = os.environ.get('SMTP_HOST', 'simulation')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'True').lower() in ('true', '1', 't')
    SMTP_USER = os.environ.get('SMTP_USER')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
    SMTP_SENDER = os.environ.get('SMTP_SENDER', os.environ.get('SMTP_USER', 'invitations@sreenidhi.edu.in'))
