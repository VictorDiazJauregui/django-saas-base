import logging
import smtplib
from threading import Thread

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


# The email is rendered here, in the caller's language, and handed to a thread after the
# commit: the response does not wait for the SMTP server, so its timing does not reveal
# whether an email went out (an account that exists or not, in a password reset).
def send_templated_email(template_prefix, recipient, context):
    message = build_templated_email(template_prefix, recipient, context)
    if not settings.EMAIL_SEND_IN_BACKGROUND:
        message.send()
        return
    transaction.on_commit(lambda: start_background_delivery(message, template_prefix))


def build_templated_email(template_prefix, recipient, context):
    subject = render_to_string(f"{template_prefix}/subject.txt", context)
    message = EmailMultiAlternatives(
        subject=" ".join(subject.split()),
        body=render_to_string(f"{template_prefix}/body.txt", context),
        to=[recipient],
    )
    html_body = render_to_string(f"{template_prefix}/body.html", context)
    message.attach_alternative(html_body, "text/html")
    return message


def start_background_delivery(message, template_prefix):
    Thread(target=deliver, args=(message, template_prefix)).start()


def deliver(message, template_prefix):
    try:
        message.send()
    except (smtplib.SMTPException, OSError):
        logger.exception("Could not send the %s email.", template_prefix)
