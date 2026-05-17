# FoodOnline — AI-Powered Multi-Vendor Food Delivery Platform

<div align="center">

![FoodOnline Banner](https://img.shields.io/badge/FoodOnline-A%20Restaurant%20Marketplace-e31837?style=for-the-badge&logo=django&logoColor=white)

[![Live Demo](https://img.shields.io/badge/Live%20Demo-foodonline--qezz.onrender.com-27ae60?style=flat-square&logo=render&logoColor=white)](https://foodonline-qezz.onrender.com)
[![Django](https://img.shields.io/badge/Django-6.0.3-092e20?style=flat-square&logo=django&logoColor=white)](https://djangoproject.com)
[![Python](https://img.shields.io/badge/Python-3.12-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-PostGIS-336791?style=flat-square&logo=postgresql&logoColor=white)](https://postgis.net)
[![Docker](https://img.shields.io/badge/Docker-Deployed-2496ed?style=flat-square&logo=docker&logoColor=white)](https://docker.com)

</div>

---

> A production-deployed multi-vendor food delivery platform built with Django 6, featuring a fully custom AI chatbot assistant, geospatial restaurant discovery, a signal-driven review system, and real-time order tracking — deployed on Render with Docker and Supabase PostgreSQL.

---

## Table of Contents

- [Live Demo](#live-demo)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [AI Chatbot System](#ai-chatbot-system)
- [Review System](#review-system)
- [Screenshots](#screenshots)
- [Project Structure](#project-structure)
- [Local Setup](#local-setup)
- [Deployment](#deployment)
- [Environment Variables](#environment-variables)

---

## Live Demo

🔗 **[foodonline-qezz.onrender.com](https://foodonline-qezz.onrender.com)**

| Role | Credentials |
|------|-------------|
| Customer | Register via signup page |
| Vendor | Register as vendor → Admin approval required |
| Admin | Contact for demo access |

---

## Features

### Core Platform
- **Role-based authentication** — Customer, Vendor, Admin with separate onboarding flows
- **Vendor approval workflow** — vendors inactive until admin approves
- **Geospatial restaurant discovery** — PostGIS-powered GPS distance sorting with city fallback
- **Multi-vendor cart** — AJAX-driven with real-time counter updates
- **Distributed checkout** — Razorpay and PayPal with multi-vendor order splitting
- **Order lifecycle** — New → Accepted → Preparing → Out for Delivery → Completed
- **Vendor dashboard** — total revenue, monthly earnings, recent orders with subtotals
- **Menu builder** — categories, food items, opening hours with overlap validation
- **Opening hours** — IST-aware open/closed detection using `timezone.localtime()`

### AI Chatbot Assistant
- **5-model fallback chain** via OpenRouter (Mistral 7B → Gemini Flash → more)
- **Role-aware prompting** — vendor and customer get completely different AI personalities
- **DB-backed rate limiting** — no Redis required, custom `RateLimitBucket` model
- **Full interaction logging** — every AI call logged with model used, response time, feature type
- **Chat history** — persists across page reloads via sessionStorage, clears on browser close
- **Voice input/output** — Web Speech API with preferred voice selection

### Customer AI Features
- **Mood-based recommendations** — "I'm feeling spicy" maps to food keyword pools
- **Exact dish matching** — "butter chicken" finds matching items before falling back to mood keywords
- **Conversational rating flow** — mood → veg/non-veg → minimum star rating → filtered cards
- **Order tracking** — last 5 orders with status timeline and vendor contact (call/email)
- **Smart reorder** — most-ordered past items with witty copy variants
- **Nearby restaurants** — GIS distance → city match → all vendors (3-strategy fallback)
- **Add to Cart from chatbot** — inline +/- quantity controls after adding

### Vendor AI Features
- **Food item generator** — describe a dish → AI returns title, description, price, category, tags
- **AI image generation** — Pollinations.ai → Foodish API → Canvas fallback chain
- **Competitor price comparison** — same-city vendor price analysis with AI summary
- **Onboarding tour** — 3-step vendor walkthrough on first login

### Review & Rating System
- **Half-star ratings** — 0.5 to 5.0 stored as `DecimalField`
- **Signal-driven reminders** — Django signal creates `ReviewReminder` on order Completed
- **Chatbot nudge** — proactively reminds customers once per session via sessionStorage flag
- **Review modal** — half-star picker, comment textarea, photo upload (Cloudinary)
- **Live avg_rating** — computed via Django `Avg` annotation, never stored
- **Order detail page** — review section for Completed orders with per-item buttons

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Django 6, GeoDjango |
| Database | PostgreSQL + PostGIS (Supabase) |
| AI / LLM | OpenRouter API (5-model fallback) |
| Media Storage | Cloudinary (production), Local (dev) |
| Payments | Razorpay, PayPal Sandbox |
| Frontend | Vanilla JS (IIFE pattern), Web Speech API |
| Deployment | Docker, Render, Gunicorn, WhiteNoise |
| Email | Brevo SMTP |
| Logging | RotatingFileHandler + AdminEmailHandler |

---

## AI Chatbot System

The chatbot is a single IIFE (Immediately Invoked Function Expression) in vanilla JS with zero dependencies.

```
User Message
    ↓
Intent Router (JS trigger arrays)
    ↓
┌─────────────────────────────────────────────────────┐
│  Mood Recommend │ Order Track │ Review Flow          │
│  Rated Recs     │ Reorder     │ Nearby Vendors       │
│  Food Generator │ Price Compare (vendor only)        │
└─────────────────────────────────────────────────────┘
    ↓ (if no intent matched)
OpenRouter API → Mistral 7B → Gemini Flash → fallback...
    ↓
AIInteractionLog (model, timing, feature, success/error)
```

---

## Review System

```
Order Status → Completed
    ↓ (Django Signal)
ReviewReminder created per order-item
    ↓
Customer opens chatbot (next visit)
    ↓
/ai/reviews/pending/ → pending_count > 0
    ↓
Nudge message fires (once per session)
    ↓
Review Modal → half-star + comment + photo
    ↓
FoodReview saved → avg_rating updated live
```

---

## Project Structure

```
foodonline/
├── accounts/          # Custom User model, UserProfile, auth views
├── vendor/            # Vendor model, opening hours, dashboard
├── menu/              # FoodItem, Category models
├── marketplace/       # Cart, AJAX cart views, storefront
├── orders/            # Order, OrderedFood, Payment, signals
├── customers/         # Customer profile, order history
├── ai_assistant/      # Full AI chatbot system
│   ├── models.py      # ChatSession, FoodReview, ReviewReminder,
│   │                  # AIInteractionLog, RateLimitBucket, OnboardingTour
│   ├── views.py       # All AI endpoints
│   ├── customer_utils.py  # Recommendation engine
│   ├── vendor_utils.py    # Price comparison, food generation
│   └── utils.py       # OpenRouter call, rate limiting
├── foodonline_main/
│   ├── settings.py        # Local development
│   ├── settings_render.py # Production (Render)
│   └── settings_build.py  # Docker build only
├── static/
│   └── ai_assistant/
│       ├── js/chatbot.js  # Full IIFE chatbot frontend
│       └── css/chatbot.css
├── templates/
├── Dockerfile
├── start.sh
└── render.yaml
```

---

## Local Setup

### Prerequisites
- Python 3.12
- PostgreSQL with PostGIS extension
- GDAL / GEOS libraries

### 1. Clone the repo
```bash
git clone https://github.com/yourusername/foodonline.git
cd foodonline
```

### 2. Create virtual environment
```bash
python -m venv env
source env/bin/activate  # Windows: env\Scripts\activate
pip install -r requirements.txt
```

### 3. Set up environment variables
Create a `.env` file in the root directory:
```env
SECRET_KEY=your-secret-key
DEBUG=True

DB_NAME=foodonline_db
DB_USER=postgres
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=5432

OPENROUTER_API_KEY=your-openrouter-key
RAZORPAY_KEY_ID=your-razorpay-key
RAZORPAY_KEY_SECRET=your-razorpay-secret
PAYPAL_CLIENT_ID=your-paypal-client-id
PAYPAL_SECRET=your-paypal-secret
```

### 4. Set up database
```bash
# Create PostgreSQL database with PostGIS
psql -U postgres
CREATE DATABASE foodonline_db;
\c foodonline_db
CREATE EXTENSION postgis;
\q
```

### 5. Run migrations and start server
```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Visit `http://127.0.0.1:8000`

---

## Deployment

Deployed on **Render** using Docker with automatic migrations on container start.

```bash
# Render uses settings_render.py automatically via:
DJANGO_SETTINGS_MODULE=foodonline_main.settings_render
```

The `start.sh` script handles:
1. `python manage.py migrate`
2. Superuser creation (if env vars set)
3. `gunicorn` startup

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | ✅ | Django secret key |
| `DEBUG` | ✅ | True (dev) / False (prod) |
| `DB_NAME` | ✅ | PostgreSQL database name |
| `DB_USER` | ✅ | Database user |
| `DB_PASSWORD` | ✅ | Database password |
| `DB_HOST` | ✅ | Database host |
| `DB_PORT` | ✅ | Database port |
| `OPENROUTER_API_KEY` | ✅ | OpenRouter API key for AI chatbot |
| `RAZORPAY_KEY_ID` | ✅ | Razorpay payment key |
| `RAZORPAY_KEY_SECRET` | ✅ | Razorpay secret |
| `PAYPAL_CLIENT_ID` | ✅ | PayPal client ID |
| `PAYPAL_SECRET` | ✅ | PayPal secret |
| `CLOUDINARY_CLOUD_NAME` | 🟡 Prod only | Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | 🟡 Prod only | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | 🟡 Prod only | Cloudinary API secret |
| `BREVO_SMTP_LOGIN` | 🟡 Prod only | Brevo SMTP login |
| `BREVO_SMTP_KEY` | 🟡 Prod only | Brevo SMTP key |

---

## Key Design Decisions

- **Half-star ratings stored as `DecimalField(0.5 step)`** — not integer×2, for readable queries
- **Review gated per order-item** — customer can review same dish again if ordered again
- **`avg_rating` via Django annotation** — never stored, always live, no stale data
- **Rate limiting without Redis** — `RateLimitBucket` model handles it at DB level
- **sessionStorage over localStorage** — chat history clears on browser close for privacy
- **3 settings files** — clean separation of dev / prod / docker-build concerns
- **IIFE chatbot** — entire frontend in one self-contained JS function, zero dependencies

---

<div align="center">

Built by **Aditya Verma** &nbsp;·&nbsp; Django 6 · GeoDjango · OpenRouter · Docker · Render

</div>