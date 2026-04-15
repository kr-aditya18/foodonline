FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libpq-dev \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# Dummy SECRET_KEY only for build time (collectstatic)
ENV SECRET_KEY=dummy-secret-key-for-build-only
ENV DEBUG=False
ENV DB_NAME=dummy
ENV DB_USER=dummy
ENV DB_PASSWORD=dummy
ENV DB_HOST=localhost
ENV DB_PORT=5432

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput --settings=foodonline_main.settings_render

EXPOSE 10000

CMD ["gunicorn", "foodonline_main.wsgi:application", "--bind", "0.0.0.0:10000", "--workers", "2", "--timeout", "120"]