# foodonline_main/settings_aws.py
# Production settings for AWS deployment (EC2 + RDS + S3).
# NOTE: this covers DB + media storage now (Phase 9). Nginx/HTTPS-related
# settings (CSRF_TRUSTED_ORIGINS, SECURE_SSL_REDIRECT, cookie security,
# email) still need finishing in Phase 10/11 once the domain/HTTPS
# decision is made — marked with TODO below.

from .settings import *
import os

DEBUG = False

ALLOWED_HOSTS = [
    '13.203.91.95',   # your Elastic IP — update if you later get a domain
    'localhost',
    '127.0.0.1',
]

# ── GDAL / GEOS (Linux paths inside Docker on EC2 — same as Render) ─────────
GDAL_LIBRARY_PATH = '/usr/lib/libgdal.so'
GEOS_LIBRARY_PATH = '/usr/lib/libgeos_c.so'

# ── Database (RDS) ────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'OPTIONS': {'sslmode': 'require'},
    }
}

# ── Static files (WhiteNoise — same pattern as Render) ──────────────────────
_whitenoise = 'whitenoise.middleware.WhiteNoiseMiddleware'
if _whitenoise not in MIDDLEWARE:
    MIDDLEWARE.insert(1, _whitenoise)

STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'foodonline_main', 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# ── Media (S3) 
INSTALLED_APPS = INSTALLED_APPS + ['storages']

AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'ap-south-1')
AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com'
AWS_DEFAULT_ACL = None          # ACLs are disabled on the bucket — matches your setup
AWS_QUERYSTRING_AUTH = False    # public URLs, no expiring signed links
AWS_S3_FILE_OVERWRITE = False   # avoids silently overwriting same-named uploads

DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/'

# ── Payments (unchanged) ────────────────────────────────────────────────────
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')
PAYPAL_MODE = 'sandbox'
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET')

# TODO (Phase 10/11): EMAIL_BACKEND (Brevo, same as settings_render.py),
# CSRF_TRUSTED_ORIGINS, SECURE_PROXY_SSL_HEADER, cookie security settings —
# depends on HTTP-only vs HTTPS decision for the Elastic IP.