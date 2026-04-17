#!/bin/bash
set -e

echo "==> Running migrations..."
python manage.py migrate \
    --settings=foodonline_main.settings_render \
    --noinput

echo "==> Loading data..."
python manage.py loaddata datadump.json \
    --settings=foodonline_main.settings_render || echo "Data already loaded or error, skipping"

echo "==> Creating superuser if not exists..."
python manage.py shell --settings=foodonline_main.settings_render << 'EOF'
from accounts.models import User
if not User.objects.filter(email='vermaadiitya13678@gmail.com').exists():
    u = User.objects.create_superuser(
        first_name='Aditya',
        last_name='Verma',
        username='vermaadiitya13678',
        email='vermaadiitya13678@gmail.com',
        password='Aditya@2004'
    )
    u.is_active = True
    u.save()
    print("Superuser created")
else:
    print("Superuser already exists")
EOF

echo "==> Starting Gunicorn..."
exec gunicorn foodonline_main.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --timeout 120 \
    --log-level info