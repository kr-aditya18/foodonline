FROM python:3.12-slim

# ── System deps ───────────────────────────────────────────────────────────────
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

ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# ── Dummy build-time env vars ─────────────────────────────────────────────────
# Email vars use Brevo placeholders now — Gmail removed completely.
ENV SECRET_KEY=dummy-secret-key-for-build-only
ENV DEBUG=False
ENV DB_NAME=dummy
ENV DB_USER=dummy
ENV DB_PASSWORD=dummy
ENV DB_HOST=localhost
ENV DB_PORT=5432
ENV BREVO_SMTP_LOGIN=dummy@example.com
ENV BREVO_SMTP_KEY=dummy-brevo-key
ENV DEFAULT_FROM_EMAIL=noreply@example.com
ENV PAYPAL_CLIENT_ID=dummy
ENV PAYPAL_SECRET=dummy
ENV RAZORPAY_KEY_ID=dummy
ENV RAZORPAY_KEY_SECRET=dummy
ENV CLOUDINARY_CLOUD_NAME=dummy
ENV CLOUDINARY_API_KEY=dummy
ENV CLOUDINARY_API_SECRET=dummy
ENV OPENROUTER_API_KEY=dummy-openrouter-key
WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install setuptools wheel numpy && \
    pip install GDAL==$(gdal-config --version) --no-build-isolation && \
    pip install -r requirements.txt

COPY . .

# ── Collect static using build settings (no Cloudinary) ──────────────────────
RUN mkdir -p /app/staticfiles && \
    python manage.py collectstatic --noinput \
        --settings=foodonline_main.settings_build

RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]