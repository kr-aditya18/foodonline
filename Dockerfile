FROM python:3.12-slim

# ── System deps: GDAL, GEOS, PROJ, PostgreSQL client, compilers ───────────────
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libpq-dev \
    gcc \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf $(find /usr/lib -name "libgdal.so*" | grep -v python | head -1) /usr/lib/libgdal.so \
    && ln -sf $(find /usr/lib -name "libgeos_c.so*" | head -1) /usr/lib/libgeos_c.so

# ── Tell GDAL pip build where headers live ────────────────────────────────────
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# ── Dummy build-time env vars ─────────────────────────────────────────────────
ENV SECRET_KEY=dummy-secret-key-for-build-only
ENV DEBUG=False
ENV DB_NAME=dummy
ENV DB_USER=dummy
ENV DB_PASSWORD=dummy
ENV DB_HOST=localhost
ENV DB_PORT=5432
ENV EMAIL_HOST=smtp.gmail.com
ENV EMAIL_PORT=587
ENV EMAIL_HOST_USER=dummy@gmail.com
ENV EMAIL_HOST_PASSWORD=dummy
ENV EMAIL_USE_TLS=True
ENV PAYPAL_CLIENT_ID=dummy
ENV PAYPAL_SECRET=dummy
ENV RAZORPAY_KEY_ID=dummy
ENV RAZORPAY_KEY_SECRET=dummy
ENV CLOUDINARY_CLOUD_NAME=dummy
ENV CLOUDINARY_API_KEY=dummy
ENV CLOUDINARY_API_SECRET=dummy

WORKDIR /app

COPY requirements.txt .

# ── Install Python deps ───────────────────────────────────────────────────────
RUN pip install --upgrade pip && \
    pip install setuptools wheel numpy && \
    pip install GDAL==$(gdal-config --version) --no-build-isolation && \
    pip install -r requirements.txt

COPY . .

# ── Create staticfiles dir and collect static ─────────────────────────────────
RUN mkdir -p /app/staticfiles && \
    python manage.py collectstatic --noinput \
    --settings=foodonline_main.settings_render

RUN chmod +x start.sh

EXPOSE 10000

CMD ["./start.sh"]