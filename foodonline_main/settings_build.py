"""
Build-only settings for Docker collectstatic step.
Bypasses Cloudinary (dummy creds) and uses local file storage.
NOT used at runtime — only during docker build.
"""

from .settings_render import *

# Override Cloudinary storage with local filesystem for build step
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# Remove cloudinary apps to avoid any cloudinary calls during build
INSTALLED_APPS = [app for app in INSTALLED_APPS
                  if app not in ('cloudinary_storage', 'cloudinary')]