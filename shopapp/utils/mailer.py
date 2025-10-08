"""Mail helper supporting SMTP (app password) and Gmail API transports."""

from __future__ import annotations

import base64
import json
import pickle
import smtplib
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from flask import current_app

try:  # Google client libraries are optional at runtime
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:  # pragma: no cover - handled gracefully
    Credentials = None  # type: ignore
    Request = None  # type: ignore
    build = None  # type: ignore
    HttpError = Exception  # type: ignore


def init_mail_settings(app) -> None:
    """Prime configuration flags so the UI can show whether mail is ready."""

    sender = app.config.get('MAIL_SENDER')
    password = app.config.get('MAIL_PASSWORD')
    transport = (app.config.get('MAIL_TRANSPORT') or 'smtp').lower()

    if transport == 'google':
        cred_path = Path(app.config.get('GOOGLE_CREDENTIALS_FILE', 'credentials.json')).expanduser()
        token_path = Path(app.config.get('GOOGLE_TOKEN_FILE', 'token.pickle')).expanduser()
        app.config['MAIL_READY'] = cred_path.exists() and token_path.exists()
    else:
        app.config['MAIL_READY'] = bool(sender and password)


def send_mail(
    to: str,
    subject: str,
    body: str,
    sender: Optional[str] = None,
    password: Optional[str] = None,
) -> bool:
    """Send an email using the configured transport.

    When `MAIL_TRANSPORT=google`, the function attempts to use the Gmail API
    with OAuth credentials (credentials.json + token.pickle). On failure it
    falls back to SMTP if credentials are available, so background jobs do not
    crash silently.
    """

    cfg = current_app.config
    chosen_transport = (cfg.get('MAIL_TRANSPORT') or 'smtp').lower()
    sender = sender or cfg.get('MAIL_SENDER')
    password = password or cfg.get('MAIL_PASSWORD')
    smtp_host = cfg.get('MAIL_SMTP', 'smtp.gmail.com')
    smtp_port = int(cfg.get('MAIL_PORT', 587))

    if chosen_transport == 'google':
        sent = _send_via_gmail_api(to, subject, body, sender)
        if sent or not (sender and password):
            return sent
        current_app.logger.warning(
            'Gmail API send failed; falling back to SMTP for %s', to
        )

    return _send_via_smtp(to, subject, body, sender, password, smtp_host, smtp_port)


def _send_via_smtp(
    to: str,
    subject: str,
    body: str,
    sender: Optional[str],
    password: Optional[str],
    host: str,
    port: int,
) -> bool:
    if not (sender and password and to):
        current_app.logger.warning('SMTP send aborted: incomplete credentials or recipient')
        return False

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = to

    try:
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, [to], msg.as_string())
        return True
    except Exception as exc:  # pragma: no cover - network failures
        current_app.logger.exception('SMTP send failed: %s', exc)
        return False


def _send_via_gmail_api(to: str, subject: str, body: str, sender: Optional[str]) -> bool:
    if build is None or Credentials is None or Request is None:
        current_app.logger.error('Gmail libraries not installed; cannot send via Gmail API')
        return False

    service = _get_gmail_service()
    if not service:
        return False

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['To'] = to
    if sender:
        msg['From'] = sender

    encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')

    try:
        service.users().messages().send(userId='me', body={'raw': encoded}).execute()
        return True
    except HttpError as exc:  # pragma: no cover - Google failure
        current_app.logger.exception('Gmail API send failed: %s', exc)
    except Exception as exc:  # pragma: no cover - unexpected failure
        current_app.logger.exception('Unexpected Gmail API error: %s', exc)
    return False


def _get_gmail_service() -> Optional[object]:
    creds = _load_gmail_credentials()
    if not creds:
        return None
    try:
        return build('gmail', 'v1', credentials=creds)
    except Exception as exc:  # pragma: no cover - client failure
        current_app.logger.exception('Failed creating Gmail service: %s', exc)
        return None


def _load_gmail_credentials() -> Optional['Credentials']:
    cfg = current_app.config
    scopes = cfg.get('GOOGLE_MAIL_SCOPES') or ['https://www.googleapis.com/auth/gmail.send']
    if isinstance(scopes, str):
        scopes = [scope.strip() for scope in scopes.split(',') if scope.strip()]

    cred_path = Path(cfg.get('GOOGLE_CREDENTIALS_FILE', 'credentials.json')).expanduser()
    token_path = Path(cfg.get('GOOGLE_TOKEN_FILE', 'token.pickle')).expanduser()

    if not cred_path.exists():
        current_app.logger.warning('Gmail API send skipped: missing %s', cred_path)
        return None

    creds: Optional[Credentials] = None
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), scopes)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            try:
                with token_path.open('rb') as fh:
                    creds = pickle.load(fh)
            except Exception as exc:
                current_app.logger.warning('Unable to read legacy token file %s: %s', token_path, exc)
                creds = None

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_path.write_text(creds.to_json())
            return creds
        except Exception as exc:  # pragma: no cover - refresh failure
            current_app.logger.exception('Failed refreshing Gmail token: %s', exc)
            return None

    current_app.logger.warning(
        'Gmail API send skipped: refresh token missing; run local OAuth flow to refresh %s',
        token_path,
    )
    return None
