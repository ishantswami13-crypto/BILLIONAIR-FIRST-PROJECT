import smtplib
from email.mime.text import MIMEText
from typing import Optional

from flask import current_app


def init_mail_settings(app) -> None:
    # Keep a flag for future health checks
    sender = app.config.get('MAIL_SENDER')
    password = app.config.get('MAIL_PASSWORD')
    app.config['MAIL_READY'] = bool(sender and password)


def send_mail(to: str, subject: str, body: str,
              sender: Optional[str] = None,
              password: Optional[str] = None) -> bool:
    cfg = current_app.config
    sender = sender or cfg.get('MAIL_SENDER')
    password = password or cfg.get('MAIL_PASSWORD')
    smtp_host = cfg.get('MAIL_SMTP', 'smtp.gmail.com')
    smtp_port = int(cfg.get('MAIL_PORT', 587))

    if not (sender and password and to):
        return False

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = to

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, [to], msg.as_string())
    return True
