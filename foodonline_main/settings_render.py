"""
Production settings for Render deployment.
Inherits from base settings.py and overrides Linux/cloud-specific config.
"""

from .settings import *
import os

# ── Security ──────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ['SECRET_KEY']
DEBUG = False

ALLOWED_HOSTS = [
    'foodonline-qezz.onrender.com',
    '.onrender.com',
    'localhost',
    '127.0.0.1',
]

# ── Proxy headers — CRITICAL for Render (sits behind load balancer) ───────────
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# ── GDAL / GEOS — Linux paths (symlinks created in Dockerfile) ────────────────
GDAL_LIBRARY_PATH = '/usr/lib/libgdal.so'
GEOS_LIBRARY_PATH = '/usr/lib/libgeos_c.so'

# ── Database (PostGIS on Neon) ────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.environ['DB_NAME'],
        'USER': os.environ['DB_USER'],
        'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': os.environ['DB_HOST'],
        'PORT': os.environ.get('DB_PORT', '5432'),
        'OPTIONS': {
            'sslmode': 'require',
            'options': '-c channel_binding=require',
        },
        'CONN_MAX_AGE': 60,
    }
}

# ── Static Files (WhiteNoise) ─────────────────────────────────────────────────
_whitenoise = 'whitenoise.middleware.WhiteNoiseMiddleware'
if _whitenoise not in MIDDLEWARE:
    MIDDLEWARE.insert(1, _whitenoise)

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = []  # CRITICAL: clear inherited value to avoid conflict

# ── Email ─────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = 'UrbanEats MarketPlace <django.UrbanEats@gmail.com>'

# ── Payments ──────────────────────────────────────────────────────────────────
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID', '')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET', '')
PAYPAL_MODE = 'sandbox'
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')

# ── CSRF ──────────────────────────────────────────────────────────────────────
CSRF_TRUSTED_ORIGINS = [
    "https://foodonline-qezz.onrender.com",
    "https://*.onrender.com",
]

# ── Security Headers ──────────────────────────────────────────────────────────
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin-allow-popups"