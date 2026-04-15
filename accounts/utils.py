# contains helper function for our code
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage
from django.conf import settings
def detectUser(user):
    if user.is_superuser:
        return '/admin/'   # optional but useful

    if user.role == 1:
        return 'vendordashboard'
    elif user.role == 2:
        return 'custdashboard'

    return 'myAccount'
        
# helper function to send mail 
# def send_verification_email(request,user,email):
#     from_email = settings.DEFAULT_FROM_EMAIL
#     current_site = get_current_site(request)
#     message = render_to_string(email_template,{
#         'user': user,
#         'domain': current_site,
#         'uid': urlsafe_base64_encode(force_bytes(user.pk)),
#         'token':default_token_generator.make_token(user)
#     })
    
#     to_email = user.email
#     mail = EmailMessage(mail_subject,message,from_email,to=[to_email])
#     mail.send()
    

def send_verification_email(request, user, mail_subject, email_template):

    from_email = settings.DEFAULT_FROM_EMAIL
    current_site = get_current_site(request)

    message = render_to_string(email_template, {
        'user': user,
        'domain': current_site.domain,
        'uid': urlsafe_base64_encode(force_bytes(user.pk)),
        'token': default_token_generator.make_token(user),
    })

    mail = EmailMessage(
        mail_subject,
        message,
        from_email,
        to=[user.email]
    )

    mail.content_subtype = "html"
    mail.send()
    
    
def send_notification(mail_subject, mail_template, context):
    from_email = settings.DEFAULT_FROM_EMAIL
    message = render_to_string(mail_template, context)
    to_email = context['to_email']  # ← bug fix: you use 'to_email' key in context
                                    # but here you had context['user'].email
                                    # which would crash for vendor emails (no 'user' key)
    mail = EmailMessage(
        mail_subject,
        message,
        from_email,
        to=[to_email]
    )
    mail.content_subtype = 'html'   # ← this was missing, emails showed raw HTML
    mail.send()