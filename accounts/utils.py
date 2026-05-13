# accounts/utils.py
import logging

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

logger = logging.getLogger('accounts.utils')


def detectUser(user):
    if user.is_superuser:
        return '/admin/'
    if user.role == 1:
        return 'vendordashboard'
    elif user.role == 2:
        return 'custdashboard'
    return 'myAccount'


def send_verification_email(request, user, mail_subject, email_template):
    """
    Sends account verification OR password reset email.

    Called from views.py exactly like this (no changes to views needed):
        send_verification_email(request, user, mail_subject, email_template)
    """
    from_email = settings.DEFAULT_FROM_EMAIL
    current_site = get_current_site(request)

    message = render_to_string(email_template, {
        'user': user,
        'domain': current_site.domain,
        'uid': urlsafe_base64_encode(force_bytes(user.pk)),
        'token': default_token_generator.make_token(user),
    })

    mail = EmailMessage(
        subject=mail_subject,
        body=message,
        from_email=from_email,
        to=[user.email],
    )
    mail.content_subtype = 'html'

    try:
        mail.send(fail_silently=False)
        logger.info(f'[EMAIL OK] subject="{mail_subject}" to={user.email}')
    except Exception as e:
        logger.error(
            f'[EMAIL FAILED] subject="{mail_subject}" to={user.email} '
            f'error={type(e).__name__}: {e}'
        )


def send_notification(mail_subject, mail_template, context):
    """
    Generic notification for vendor/customer/order events.

    Called from views like (no changes to views needed):
        send_notification(mail_subject, mail_template, {'to_email': '...', ...})

    IMPORTANT: context dict MUST contain a 'to_email' key.
    """
    from_email = settings.DEFAULT_FROM_EMAIL
    message = render_to_string(mail_template, context)
    to_email = context['to_email']

    mail = EmailMessage(
        subject=mail_subject,
        body=message,
        from_email=from_email,
        to=[to_email],
    )
    mail.content_subtype = 'html'

    try:
        mail.send(fail_silently=False)
        logger.info(f'[NOTIFICATION OK] subject="{mail_subject}" to={to_email}')
    except Exception as e:
        logger.error(
            f'[NOTIFICATION FAILED] subject="{mail_subject}" to={to_email} '
            f'error={type(e).__name__}: {e}'
        )