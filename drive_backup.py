"""Utility for backing up the local SQLite database to Google Drive.

The job is triggered nightly by APScheduler (see shopapp.__init__), but it can
also be run manually::

    python drive_backup.py

For the upload to work you must provide credentials.json (client secrets from
Google Cloud) and the first run will create/refresh 	oken.pickle. When the
files or Google access are missing, the backup quietly aborts instead of crashing
scheduled jobs.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import pickle
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# Project paths
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "shop.db"
BACKUP_DIR = BASE_DIR / "backups"
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.pickle"

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

logger = logging.getLogger(__name__)


def _write_token(creds: Credentials) -> None:
    """Persist credentials to TOKEN_FILE in JSON format."""
    TOKEN_FILE.write_text(creds.to_json())


def _load_credentials() -> Optional[Credentials]:
    """Return valid Google credentials or `None` when unavailable."""
    if not CREDENTIALS_FILE.exists():
        logger.warning("Google Drive backup skipped: missing %s", CREDENTIALS_FILE)
        return None

    creds: Optional[Credentials] = None
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            try:
                with TOKEN_FILE.open("rb") as fh:
                    creds = pickle.load(fh)
            except Exception as exc:
                logger.warning("Unable to read legacy token file %s: %s", TOKEN_FILE, exc)
                creds = None

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _write_token(creds)
            return creds
        except Exception as exc:  # pragma: no cover - network/Google failure
            logger.exception("Failed refreshing Google token: %s", exc)
            return None

    # No valid cached credentials; start OAuth flow (interactive)
    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
        creds = flow.run_local_server(port=0)
        _write_token(creds)
        return creds
    except Exception as exc:  # pragma: no cover - interactive failure
        logger.exception("Unable to obtain Google credentials: %s", exc)
        return None


def _get_drive_service() -> Optional[object]:
    creds = _load_credentials()
    if not creds:
        return None
    try:
        return build("drive", "v3", credentials=creds)
    except Exception as exc:  # pragma: no cover - Google client failure
        logger.exception("Google Drive service creation failed: %s", exc)
        return None


def backup_to_drive() -> bool:
    """Upload a timestamped copy of `shop.db` to Google Drive."""
    if not DB_PATH.exists():
        logger.warning("Google Drive backup skipped: database %s not found", DB_PATH)
        return False

    service = _get_drive_service()
    if not service:
        # Details already logged; keep scheduler alive
        return False

    BACKUP_DIR.mkdir(exist_ok=True)
    now_utc = _dt.datetime.now(_dt.timezone.utc)
    backup_name = f"shop_backup_{now_utc:%Y-%m-%d_%H%M%S}.db"
    backup_path = BACKUP_DIR / backup_name

    backup_path.write_bytes(DB_PATH.read_bytes())

    media = MediaFileUpload(str(backup_path), mimetype="application/x-sqlite3")
    metadata = {"name": backup_name}

    try:
        created = service.files().create(body=metadata, media_body=media, fields="id").execute()
        file_id = created.get("id")
        logger.info("Backup uploaded to Google Drive (id=%s)", file_id)
        return True
    except HttpError as exc:  # pragma: no cover - network/Google failure
        logger.exception("Google Drive upload failed: %s", exc)
    except Exception as exc:  # pragma: no cover - unexpected failure
        logger.exception("Unexpected error during Drive backup: %s", exc)

    return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    success = backup_to_drive()
    if success:
        print("Backup completed successfully.")
    else:
        print("Backup skipped or failed. See logs for details.")
