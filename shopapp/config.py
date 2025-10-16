import os
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env', override=False)

LOCAL_ENV = BASE_DIR / '.env.local'
if LOCAL_ENV.exists():
    load_dotenv(LOCAL_ENV, override=True)


class BaseConfig:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', f"sqlite:///{BASE_DIR / 'shop.db'}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADVANCED_MODE = os.getenv('ADVANCED_MODE', 'off').lower()
    TIMEZONE = os.getenv('TZ', 'UTC')

    DEFAULT_ADMIN_USERNAME = os.getenv('DEFAULT_ADMIN_USERNAME', 'admin')
    DEFAULT_ADMIN_PASSWORD = os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin123')
    DEFAULT_ADMIN_EMAIL = os.getenv('DEFAULT_ADMIN_EMAIL', 'admin@example.com')

    STRIPE_CHECKOUT_URL = os.getenv('STRIPE_CHECKOUT_URL')
    RAZORPAY_PAYMENT_LINK = os.getenv('RAZORPAY_PAYMENT_LINK')
    PAYMENT_LINK = (
        os.getenv('PAYMENT_LINK')
        or STRIPE_CHECKOUT_URL
        or RAZORPAY_PAYMENT_LINK
    )
    WAITLIST_URL = os.getenv('WAITLIST_URL')
    DEMO_GIF_URL = os.getenv('DEMO_GIF_URL', 'https://media.giphy.com/media/tXL4FHPSnVJ0A/giphy.gif')
    PRODUCT_NAME = os.getenv('PRODUCT_NAME', 'ShopApp SaaS')
    PRODUCT_TAGLINE = os.getenv('PRODUCT_TAGLINE', 'Retail OS for high-velocity stores')

    GA_MEASUREMENT_ID = os.getenv('GA_MEASUREMENT_ID')
    MIXPANEL_TOKEN = os.getenv('MIXPANEL_TOKEN')
    EXTRA_PLAN_FEATURES = {}

    WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
    WHATSAPP_INSTANCE_ID = os.getenv('WHATSAPP_INSTANCE_ID')
    WHATSAPP_API_URL = os.getenv('WHATSAPP_API_URL')
    WHATSAPP_DEFAULT_COUNTRY_CODE = os.getenv('WHATSAPP_DEFAULT_COUNTRY_CODE', '+91')
    WHATSAPP_REMINDER_COOLDOWN_HOURS = int(os.getenv('WHATSAPP_REMINDER_COOLDOWN_HOURS', '24'))

    APP_VERSION = os.getenv('APP_VERSION', '1.0.0')
    ACTIVE_PLAN = os.getenv('ACTIVE_PLAN', 'pro')
    DATA_ENCRYPTION_NOTICE = os.getenv('DATA_ENCRYPTION_NOTICE', 'Your data is encrypted with AES-256.')

    COPYRIGHT_YEAR = os.getenv('COPYRIGHT_YEAR', str(datetime.utcnow().year))

    MAIL_TRANSPORT = os.getenv('MAIL_TRANSPORT', 'console')
    MAIL_SMTP = os.getenv('MAIL_SMTP', 'smtp.mailtrap.io')
    MAIL_PORT = int(os.getenv('MAIL_PORT', '587'))
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
    MAIL_SENDER = os.getenv('MAIL_SENDER', 'no-reply@example.local')
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)


class DevConfig(BaseConfig):
    DEBUG = True


class ProdConfig(BaseConfig):
    DEBUG = False


Config = DevConfig if os.getenv('FLASK_ENV') != 'production' else ProdConfig




