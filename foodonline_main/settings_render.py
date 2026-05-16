# foodonline_main/settings_render.py
# Production settings for Render deployment — Brevo email only, no Gmail.

from .settings import *
import os

# ── Timezone ──────────────────────────────────────────────────────────────────
TIME_ZONE = 'Asia/Kolkata'
USE_TZ = True

# ── Security ──────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get('SECRET_KEY')
DEBUG = False

ALLOWED_HOSTS = [
    'foodonline-qezz.onrender.com',
    '.onrender.com',
    'localhost',
    '127.0.0.1',
]

# ── Proxy headers (Render sits behind a load balancer) ───────────────────────
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# ── GDAL / GEOS (Linux paths inside Docker) ───────────────────────────────────
GDAL_LIBRARY_PATH = '/usr/lib/libgdal.so'
GEOS_LIBRARY_PATH = '/usr/lib/libgeos_c.so'

# ── Database (Supabase session pooler) ────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': 0,
        'OPTIONS': {
            'sslmode': 'require',
            'keepalives': 1,
            'keepalives_idle': 30,
            'keepalives_interval': 10,
            'keepalives_count': 5,
        },
    }
}

# ── Cloudinary apps (must be before staticfiles) ──────────────────────────────
_cloudinary_apps = ['cloudinary_storage', 'cloudinary']
for _app in reversed(_cloudinary_apps):
    if _app not in INSTALLED_APPS:
        _idx = INSTALLED_APPS.index('django.contrib.staticfiles')
        INSTALLED_APPS.insert(_idx, _app)

# ── WhiteNoise middleware ──────────────────────────────────────────────────────
_whitenoise = 'whitenoise.middleware.WhiteNoiseMiddleware'
if _whitenoise not in MIDDLEWARE:
    MIDDLEWARE.insert(1, _whitenoise)

# ── Static files ──────────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'foodonline_main', 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# ── Media (Cloudinary) ────────────────────────────────────────────────────────
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME'),
    'API_KEY':    os.environ.get('CLOUDINARY_API_KEY'),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET'),
}
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = 'smtp-relay.brevo.com'
EMAIL_PORT          = 2525
EMAIL_USE_TLS       = True
EMAIL_USE_SSL       = False
EMAIL_HOST_USER     = os.environ.get('BREVO_SMTP_LOGIN')
EMAIL_HOST_PASSWORD = os.environ.get('BREVO_SMTP_KEY')
EMAIL_TIMEOUT       = 30
DEFAULT_FROM_EMAIL  = os.environ.get('DEFAULT_FROM_EMAIL', 'UrbanEats <django.urbaneats@gmail.com>')

# ── Logging — visible in Render log dashboard ─────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {name} — {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        # Shows exact SMTP errors from Django's mail module
        'django.core.mail': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        # Shows [EMAIL OK] / [EMAIL FAILED] lines from utils.py
        'accounts.utils': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        # General Django warnings/errors
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': True,
        },
        'ai_assistant': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

# chatbot keys
OPENROUTER_API_KEY = config('OPENROUTER_API_KEY', default='')

# ── Payments (unchanged) ──────────────────────────────────────────────────────
PAYPAL_CLIENT_ID  = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET     = os.environ.get('PAYPAL_SECRET')
PAYPAL_MODE       = 'sandbox'
RAZORPAY_KEY_ID     = os.environ.get('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET')

# ── CSRF ──────────────────────────────────────────────────────────────────────
CSRF_TRUSTED_ORIGINS = [
    'https://foodonline-qezz.onrender.com',
    'https://*.onrender.com',
]

# ── Security headers ──────────────────────────────────────────────────────────
SECURE_PROXY_SSL_HEADER           = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT               = False
SESSION_COOKIE_SECURE             = True
CSRF_COOKIE_SECURE                = True
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin-allow-popups'

# ── Phase 10: Admin email alerts (production) ────────────────────────────────
ADMINS = [
    ('FoodOnline Admin', os.environ.get('ADMIN_EMAIL', '')),
]
MANAGERS = ADMINS

# ── Phase 10: Rate limits (production — slightly tighter) ────────────────────
AI_RATE_LIMITS = {
    'user_per_minute': 10,
    'user_per_day':    200,
    'guest_per_day':   20,
}

# ── Phase 10: Logging (production — file + console + email on ERROR) ─────────
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {name} {process:d} {thread:d} — {message}',
            'style': '{',
        },
        'simple': {
            'format': '[{levelname}] {asctime} {name} — {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    'handlers': {
        # Render log dashboard
        'console': {
            'class':     'logging.StreamHandler',
            'formatter': 'simple',
        },
        # Rotating file — 5 MB max, keep 5 backups
        'ai_file': {
            'class':       'logging.handlers.RotatingFileHandler',
            'filename':    os.path.join(LOGS_DIR, 'ai_assistant.log'),
            'maxBytes':    5 * 1024 * 1024,
            'backupCount': 5,
            'formatter':   'verbose',
            'encoding':    'utf-8',
        },
        'django_file': {
            'class':       'logging.handlers.RotatingFileHandler',
            'filename':    os.path.join(LOGS_DIR, 'django.log'),
            'maxBytes':    5 * 1024 * 1024,
            'backupCount': 3,
            'formatter':   'verbose',
            'encoding':    'utf-8',
        },
        # Email ADMINS on ERROR and above (uses your Brevo SMTP)
        'mail_admins': {
            'class':       'django.utils.log.AdminEmailHandler',
            'filters':     ['require_debug_false'],
            'formatter':   'verbose',
            'level':       'ERROR',
            'include_html': True,
        },
    },
    'loggers': {
        'ai_assistant': {
            'handlers':  ['console', 'ai_file', 'mail_admins'],
            'level':     'DEBUG',
            'propagate': False,
        },
        'django': {
            'handlers':  ['console', 'django_file'],
            'level':     'WARNING',
            'propagate': True,
        },
        'django.request': {
            'handlers':  ['mail_admins', 'django_file'],
            'level':     'ERROR',
            'propagate': False,
        },
        'django.core.mail': {
            'handlers':  ['console'],
            'level':     'DEBUG',
            'propagate': True,
        },
        'accounts.utils': {
            'handlers':  ['console', 'django_file'],
            'level':     'DEBUG',
            'propagate': True,
        },
    },
}