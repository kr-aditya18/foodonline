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
    'foodonline-qezz.onrender.com',   # add exact domain explicitly
    '.onrender.com',
    'localhost',
    '127.0.0.1',
]

# ── GDAL / GEOS / PROJ — Linux paths ─────────────────────────────────────────
GDAL_LIBRARY_PATH = '/usr/lib/libgdal.so'      # symlink created in Dockerfile
GEOS_LIBRARY_PATH = '/usr/lib/libgeos_c.so'    # symlink created in Dockerfile

# PROJ is usually found automatically; only add if you get a PROJ error:
# PROJ_LIBRARY_PATH = '/usr/lib/x86_64-linux-gnu/libproj.so'

# ── Database (PostGIS on Neon) ─────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.environ['DB_NAME'],
        'USER': os.environ['DB_USER'],
        'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': os.environ['DB_HOST'],
        'PORT': os.environ.get('DB_PORT', '5432'),
        'OPTIONS': {
            'sslmode': 'require',   # Neon requires SSL
        },
        'CONN_MAX_AGE': 60,         # Keep connections alive 60s (good for serverless)
    }
}

# ── Static Files (WhiteNoise) ─────────────────────────────────────────────────
# Insert WhiteNoise AFTER SecurityMiddleware (index 1)
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
STATIC_ROOT = BASE_DIR / 'staticfiles'   # Use 'staticfiles' not 'static' on Render

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

CSRF_TRUSTED_ORIGINS = [
    "https://foodonline-qezz.onrender.com",
    "https://*.onrender.com",
]

# ── Security Headers (production best practice) ───────────────────────────────
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin-allow-popups"