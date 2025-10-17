from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from flask import current_app


class GSTIntegrationError(RuntimeError):
    """Raised when the GST integration encounters a recoverable error."""


@dataclass(frozen=True)
class GSTCredentials:
    provider: str
    username: Optional[str]
    password: Optional[str]
    client_id: Optional[str]
    client_secret: Optional[str]
    sandbox_mode: bool


def _load_credentials() -> GSTCredentials:
    cfg = current_app.config
    return GSTCredentials(
        provider=cfg.get("GST_PROVIDER", "nic"),
        username=cfg.get("GST_USERNAME"),
        password=cfg.get("GST_PASSWORD"),
        client_id=cfg.get("GST_CLIENT_ID"),
        client_secret=cfg.get("GST_CLIENT_SECRET"),
        sandbox_mode=str(cfg.get("GST_SANDBOX", "true")).lower() == "true",
    )


class GSTService:
    """Facade for GST e-invoice and e-way integrations.

    Implementation is intentionally stubbed; vendor-specific glue will be filled in upcoming iterations.
    """

    def __init__(self, credentials: GSTCredentials) -> None:
        self._credentials = credentials
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    # Token helpers -----------------------------------------------------------------
    def ensure_token(self) -> str:
        if self._access_token and self._token_expiry and self._token_expiry > datetime.utcnow():
            return self._access_token
        # Placeholder: connect to provider, exchange credentials, set expiry.
        self._access_token = "stub-token"
        self._token_expiry = datetime.utcnow()
        return self._access_token

    # E-invoice ---------------------------------------------------------------------
    def submit_einvoice(self, sale_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit invoice payload to GST system. Returns provider echo response."""
        self.ensure_token()
        # TODO: Call provider endpoint; log request/response; raise GSTIntegrationError on failure.
        return {"status": "queued", "sale_id": sale_id, "provider": self._credentials.provider}

    def fetch_status(self, irn: str) -> Dict[str, Any]:
        """Fetch current status of an IRN from the provider."""
        self.ensure_token()
        return {"irn": irn, "status": "unknown"}

    # E-way bill --------------------------------------------------------------------
    def generate_eway_bill(self, sale_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.ensure_token()
        return {"status": "queued", "sale_id": sale_id}

    # Utility -----------------------------------------------------------------------
    def is_configured(self) -> bool:
        cred = self._credentials
        return bool(cred.username and cred.password and cred.client_id and cred.client_secret)


def get_gst_service() -> GSTService:
    return GSTService(_load_credentials())
