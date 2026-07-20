# FoodOnline

A multi-vendor food delivery platform with geospatial restaurant discovery, a custom AI chatbot, and a self-managed AWS deployment.

**Live:** [foodonline.online](https://foodonline.online)
**Author:** [Aditya Verma](https://github.com/kr-aditya18)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Infrastructure](#infrastructure)
- [Engineering Notes](#engineering-notes)
- [Local Setup](#local-setup)

---

## Overview

FoodOnline is a Django-based food delivery marketplace supporting multiple vendors, geospatial search, and online payments. The application is deployed on AWS using infrastructure designed and provisioned manually: a custom VPC with public/private subnets, IAM users scoped to least privilege, a Dockerized deployment behind Nginx, and a GitHub Actions CI/CD pipeline that deploys on every push to `main`.

## Architecture

![AWS Architecture Diagram](./images/aws-architecture.png)

- Custom VPC (`ap-south-1`, Mumbai) with public and private subnets
- EC2 instance running the Dockerized Django app behind Nginx, with SSL via Let's Encrypt
- RDS PostgreSQL/PostGIS instance in a private subnet, reachable only from EC2 via security group rules
- S3 for media storage, accessed through a scoped IAM user
- GitHub Actions handles build and deployment on every push to `main`

## Features

**Customer**
- Geospatial restaurant discovery, sorted by distance (PostGIS)
- Multi-vendor cart with split checkout
- Razorpay / PayPal payment integration
- Order tracking with live status updates
- Half-star review system with photo uploads

**Vendor**
- Admin-approved onboarding
- Revenue and order analytics dashboard
- Menu builder with opening-hours validation
- AI-assisted listing generation (title, description, price, tags from a short input)

**AI Chatbot**
- Built without a third-party chatbot SDK
- Mood-based food recommendations
- Conversational order tracking, reorder, and review prompts
- Vendor-side competitor price comparison
- Database-backed rate limiting and interaction logging

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 6, GeoDjango |
| Database | PostgreSQL + PostGIS (AWS RDS) |
| Infrastructure | AWS (EC2, RDS, S3, VPC, IAM), Docker, Nginx |
| CI/CD | GitHub Actions |
| AI / LLM | OpenRouter API (5-model fallback chain) |
| Payments | Razorpay, PayPal Sandbox |
| Email | Brevo SMTP |
| Frontend | Vanilla JS, Web Speech API |

## Infrastructure

- **Compute:** EC2 (t3.micro), Docker container running Gunicorn behind Nginx
- **Database:** RDS PostgreSQL + PostGIS, single-AZ, private subnet, no public access
- **Storage:** S3 for media and static files, scoped IAM policy
- **Networking:** Custom VPC, public/private subnet split, chained security groups
- **CI/CD:** GitHub Actions — build, push, and deploy on every commit to `main`

## Engineering Notes

- **S3 upload bug:** Django 4.2+'s `STORAGES` setting silently overrides the older `DEFAULT_FILE_STORAGE` setting. Uploads were writing to the container's local disk instead of S3, with no errors raised, and were lost on every redeploy. Found by testing `boto3` directly, bypassing Django's storage abstraction.
- **Port 8000 unreachable externally:** security group rules were correct, but the app was still unreachable from outside EC2. Root cause was the ISP throttling non-standard high ports. Resolved by routing through Nginx on ports 80/443.
- **Nginx multi-domain conflict:** running Certbot for multiple domains produced overlapping `server_name` blocks, causing requests to the bare IP to 404 silently. Resolved by consolidating the routing configuration.

## Local Setup

\`\`\`bash
git clone https://github.com/kr-aditya18/foodonline.git
cd foodonline
python -m venv env && source env/bin/activate  # Windows: env\Scripts\activate
pip install -r requirements.txt
\`\`\`

Create a \`.env\` file:

\`\`\`env
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
\`\`\`

Requires PostgreSQL with the PostGIS extension enabled locally.

\`\`\`bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
\`\`\`

Visit \`http://127.0.0.1:8000\`.

---

Built by [Aditya Verma](https://github.com/kr-aditya18)
