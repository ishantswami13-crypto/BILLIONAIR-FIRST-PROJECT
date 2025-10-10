from __future__ import annotations

import logging
from typing import Optional

import requests
from flask import current_app

logger = logging.getLogger(__name__)


def send_whatsapp_message(phone: str, message: str) -> bool:
    """Send a WhatsApp message using the configured provider.

    Supports UltraMsg-style simple API (token + instance) or a generic POST URL.
    """

    if not phone or not message:
        logger.warning("WhatsApp send aborted: missing phone or message")
        return False

    token = current_app.config.get("WHATSAPP_TOKEN")
    instance_id = current_app.config.get("WHATSAPP_INSTANCE_ID")
    api_url = current_app.config.get("WHATSAPP_API_URL")
    if not api_url:
        if not (token and instance_id):
            logger.info("WhatsApp config missing; reminders disabled")
            return False
        api_url = f"https://api.ultramsg.com/{instance_id}/messages/chat"

    payload = {
        "to": phone,
        "body": message,
    }
    headers = {}
    if token and "Authorization" not in headers:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.post(api_url, data=payload, headers=headers, timeout=10)
        if resp.status_code >= 400:
            logger.warning("WhatsApp API error %s: %s", resp.status_code, resp.text)
            return False
        return True
    except Exception as exc:  # pragma: no cover
        logger.exception("WhatsApp send failure: %s", exc)
        return False
