#!/bin/bash
set -e

echo "==> Running migrations..."
python manage.py migrate --settings=foodonline_main.settings_render --noinput

echo "==> Starting Gunicorn..."
exec gunicorn foodonline_main.wsgi:application \
    --bind 0.0.0.0:10000 \
    --workers 2 \
    --timeout 120 \
    --log-level info