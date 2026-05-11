#!/bin/bash
set -e

echo "==> Running migrations..."
python manage.py migrate \
    --settings=foodonline_main.settings_render \
    --noinput

echo "==> Creating superuser if not exists..."
python manage.py shell --settings=foodonline_main.settings_render << 'EOF'
import os
from accounts.models import User
email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
if email and not User.objects.filter(email=email).exists():
    u = User.objects.create_superuser(
        first_name=os.environ.get('DJANGO_SUPERUSER_FIRST_NAME', ''),
        last_name=os.environ.get('DJANGO_SUPERUSER_LAST_NAME', ''),
        username=os.environ.get('DJANGO_SUPERUSER_USERNAME', ''),
        email=email,
        password=password
    )
    u.is_active = True
    u.save()
    print("Superuser created")
else:
    print("Superuser already exists")
EOF

echo "==> Checking email config..."
python manage.py shell --settings=foodonline_main.settings_render << 'EOF'
from django.conf import settings
print("EMAIL_HOST:", settings.EMAIL_HOST)
print("EMAIL_PORT:", settings.EMAIL_PORT)
print("EMAIL_HOST_USER:", settings.EMAIL_HOST_USER)
print("EMAIL_BACKEND:", settings.EMAIL_BACKEND)
EOF

echo "==> Starting Gunicorn..."
exec gunicorn foodonline_main.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --timeout 120 \
    --log-level info