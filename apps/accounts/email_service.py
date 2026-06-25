"""
Email service for account/credential delivery.

Uses Django's configured EMAIL_BACKEND:
  - dev   -> console backend (prints to terminal, no SMTP)
  - prod  -> SMTP backend (set via environment, see settings)
Callers should treat email as best-effort and not let failures break the
surrounding business transaction.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _send_html(*, subject, to_email, text_body, template, context):
    """Send a multipart email: plain-text body + HTML alternative from a template."""
    html_body = render_to_string(template, context)
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)


def send_student_credentials(
    *,
    to_email: str,
    student_name: str,
    student_id: str,
    login_email: str,
    temporary_password: str,
) -> None:
    """Email a newly admitted student their login credentials."""
    context = {
        "student_name": student_name,
        "student_id": student_id,
        "login_email": login_email,
        "temporary_password": temporary_password,
    }
    text_body = (
        f"Dear {student_name or 'Student'},\n\n"
        f"Your student account has been created.\n\n"
        f"Student ID:         {student_id}\n"
        f"Login Email:        {login_email}\n"
        f"Temporary Password: {temporary_password}\n\n"
        f"Please log in and change your password immediately.\n"
    )
    _send_html(
        subject="Welcome to College",
        to_email=to_email,
        text_body=text_body,
        template="emails/student_credentials.html",
        context=context,
    )


def send_password_reset_email(*, to_email: str, reset_link: str) -> None:
    """Email a password-reset link (skeleton for the reset flow)."""
    text_body = (
        "We received a request to reset your password.\n\n"
        f"Reset link: {reset_link}\n\n"
        "If you did not request this, you can ignore this email.\n"
    )
    _send_html(
        subject="Password Reset",
        to_email=to_email,
        text_body=text_body,
        template="emails/password_reset.html",
        context={"reset_link": reset_link},
    )
