"""
Production settings for Render deployment.
"""

from .settings import *
import os

# ── Security ────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get('SECRET_KEY')
DEBUG = False

ALLOWED_HOSTS = [
    'foodonline-qezz.onrender.com',
    '.onrender.com',
    'localhost',
    '127.0.0.1',
]

# ── Proxy headers (Render behind load balancer) ─────────────────────────────
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# ── GDAL / GEOS (Linux paths) ───────────────────────────────────────────────
GDAL_LIBRARY_PATH = '/usr/lib/libgdal.so'
GEOS_LIBRARY_PATH = '/usr/lib/libgeos_c.so'

# ── Database (Neon PostGIS) ────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'OPTIONS': {
            'sslmode': 'require',
            'channel_binding': 'disable',
        },
    }
}

# ── Cloudinary Apps (before staticfiles) ────────────────────────────────────
_cloudinary_apps = [
    'cloudinary_storage',
    'cloudinary',
]

for _app in reversed(_cloudinary_apps):
    if _app not in INSTALLED_APPS:
        _staticfiles_index = INSTALLED_APPS.index('django.contrib.staticfiles')
        INSTALLED_APPS.insert(_staticfiles_index, _app)

# ── WhiteNoise (static files) ───────────────────────────────────────────────
_whitenoise = 'whitenoise.middleware.WhiteNoiseMiddleware'
if _whitenoise not in MIDDLEWARE:
    MIDDLEWARE.insert(1, _whitenoise)

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = []
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ── Media (Cloudinary) ──────────────────────────────────────────────────────
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY'),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET'),
}

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# ── Email ───────────────────────────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = True

DEFAULT_FROM_EMAIL = 'UrbanEats MarketPlace <django.UrbanEats@gmail.com>'

# ── Payments ────────────────────────────────────────────────────────────────
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')
PAYPAL_MODE = 'sandbox'

RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET')

# ── CSRF ────────────────────────────────────────────────────────────────────
CSRF_TRUSTED_ORIGINS = [
    "https://foodonline-qezz.onrender.com",
    "https://*.onrender.com",
]

# ── Security Headers ────────────────────────────────────────────────────────
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin-allow-popups"