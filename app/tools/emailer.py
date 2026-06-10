from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.config import Settings
from app.schemas import EmailStatus


def send_report_if_configured(settings: Settings, subject: str, markdown: str) -> EmailStatus:
    if not settings.smtp_configured():
        return EmailStatus(status="skipped", detail="SMTP settings are incomplete or placeholders.")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = settings.report_email_to
    message.set_content(markdown)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
        return EmailStatus(status="sent", detail=f"Sent to {settings.report_email_to}")
    except Exception as exc:
        return EmailStatus(status="error", detail=str(exc))
