from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from typing import Optional

from flask import current_app


def init_mail_settings(app) -> None:
    transport = (app.config.get('MAIL_TRANSPORT') or 'console').lower()
    if transport == 'smtp':
        ready = bool(
            app.config.get('MAIL_SMTP')
            and app.config.get('MAIL_PORT')
            and app.config.get('MAIL_SENDER')
            and app.config.get('MAIL_USERNAME')
            and app.config.get('MAIL_PASSWORD')
        )
    else:
        ready = True
    app.config['MAIL_READY'] = ready


def _smtp_send(to_email: str, subject: str, body: str) -> bool:
    cfg = current_app.config
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = cfg.get('MAIL_SENDER')
    msg['To'] = to_email

    try:
        with smtplib.SMTP(cfg['MAIL_SMTP'], cfg['MAIL_PORT']) as smtp:
            smtp.starttls()
            username: Optional[str] = cfg.get('MAIL_USERNAME')
            password: Optional[str] = cfg.get('MAIL_PASSWORD')
            if username and password:
                smtp.login(username, password)
            smtp.send_message(msg)
        return True
    except Exception as exc:  # pragma: no cover
        current_app.logger.exception('❌ SMTP send failed: %s', exc)
        return False


def send_mail(to_email: str, subject: str, body: str) -> bool:
    transport = current_app.config.get('MAIL_TRANSPORT', 'console').lower()

    if transport == 'console':
        current_app.logger.info('[MAIL console] %s → %s :: %s', to_email, subject, body)
        return True

    if transport == 'smtp':
        return _smtp_send(to_email, subject, body)

    current_app.logger.error('Unknown MAIL_TRANSPORT: %r', transport)
    return False


def send_otp_email(email: str, code: str) -> bool:
    subject = 'Your One-Time Password'
    body = f'Your OTP is: {code}\nThis code expires in 5 minutes.'
    sent = send_mail(email, subject, body)
    if current_app.debug:
        current_app.logger.info('[OTP] sent=%s %s → %s', sent, email, code)
    return sent
