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

    # Base URL for scan verification QR link
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')

    # Upload configurations
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB
    ALLOWED_EXTENSIONS = {'xlsx'}

    # Barcode path (located inside static/barcodes for easy web serving)
    BARCODE_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static', 'barcodes')

    # Mail configurations (SMTP protocol matching helpdesk, accommodating both SMTP_* and MAIL_* env variables)
    SMTP_HOST = os.environ.get('SMTP_HOST', os.environ.get('MAIL_SERVER', 'simulation'))
    SMTP_PORT = int(os.environ.get('SMTP_PORT', os.environ.get('MAIL_PORT', 587)))
    SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', os.environ.get('MAIL_USE_TLS', 'True')).lower() in ('true', '1', 't')
    SMTP_USER = os.environ.get('SMTP_USER', os.environ.get('MAIL_USERNAME'))
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', os.environ.get('MAIL_PASSWORD'))
    SMTP_SENDER = os.environ.get('SMTP_SENDER', os.environ.get('MAIL_DEFAULT_SENDER', os.environ.get('SMTP_USER', os.environ.get('MAIL_USERNAME', 'invitations@sreenidhi.edu.in'))))

    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    SMTP_BATCH_LIMIT = int(os.environ.get('SMTP_BATCH_LIMIT', 100))
    SMTP_RATE_DELAY = float(os.environ.get('SMTP_RATE_DELAY', 1.0))

    # WhatsApp configurations (Unified Messaging Platform)
    WHATSAPP_PROVIDER = os.environ.get('WHATSAPP_PROVIDER', 'simulation')
    WHATSAPP_API_URL = os.environ.get('WHATSAPP_API_URL', 'https://103.229.250.150/unified/v2/send')
    WHATSAPP_CLIENT_ID = os.environ.get('WHATSAPP_CLIENT_ID', 'sreenidhiclgbepfs44jy504')
    WHATSAPP_CLIENT_PASSWORD = os.environ.get('WHATSAPP_CLIENT_PASSWORD', 'wm84r8yhj9mzp9m1yrm78fqhpmzb8on0')
    WHATSAPP_FROM_NUMBER = os.environ.get('WHATSAPP_FROM_NUMBER', '919133386678')
    WHATSAPP_TEMPLATE_ID = os.environ.get('WHATSAPP_TEMPLATE_ID', '1773697')
    WHATSAPP_TEST_NUMBER = os.environ.get('WHATSAPP_TEST_NUMBER', os.environ.get('SMS_TEST_NUMBER'))
    WHATSAPP_RATE_DELAY = float(os.environ.get('WHATSAPP_RATE_DELAY', 1.0))
    WHATSAPP_BATCH_LIMIT = int(os.environ.get('WHATSAPP_BATCH_LIMIT', 100))
    WHATSAPP_TOKEN = os.environ.get('WHATSAPP_TOKEN')
    WHATSAPP_DLR_URL = os.environ.get('WHATSAPP_DLR_URL', '')

