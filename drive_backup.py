"""Utility for backing up the local SQLite database to Google Drive.

The job is triggered nightly by APScheduler (see shopapp.__init__), but it can
also be run manually::

    python drive_backup.py
    python drive_backup.py purge --limit 7

Every backup is a ZIP archive that bundles ``shop.db`` and a manifest file. The
script keeps the most recent seven archives by default and exposes a purge
command for manual maintenance.

For the upload to work you must provide credentials.json (client secrets from
Google Cloud) and the first run will create/refresh token.pickle. When the
files or Google access are missing, the backup quietly aborts instead of crashing
scheduled jobs.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import pickle
import sys
import zipfile
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
        return build("drive", "v3", credentials=creds)  # type: ignore[no-untyped-call]
    except Exception as exc:  # pragma: no cover - Google client failure
        logger.exception("Google Drive service creation failed: %s", exc)
        return None


def _build_archive(now_utc: _dt.datetime) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    archive_name = f"shop_backup_{now_utc:%Y-%m-%d_%H%M%S}.zip"
    archive_path = BACKUP_DIR / archive_name

    try:
        db_size = DB_PATH.stat().st_size
    except OSError:
        db_size = None

    manifest = {
        "created_at": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "database": {
            "path": str(DB_PATH),
            "size_bytes": db_size,
        },
        "version": 1,
    }

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(DB_PATH, arcname="shop.db")
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))

    return archive_path


def purge_old_backups(limit: int = 7) -> list[Path]:
    """Delete the oldest backup archives, keeping ``limit`` most recent copies."""
    BACKUP_DIR.mkdir(exist_ok=True)
    if limit < 0:
        limit = 0

    def _mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    archives = sorted(
        BACKUP_DIR.glob("shop_backup_*.zip"),
        key=_mtime,
        reverse=True,
    )

    removed: list[Path] = []
    for candidate in archives[limit:]:
        try:
            candidate.unlink()
            removed.append(candidate)
        except OSError as exc:  # pragma: no cover - filesystem permissions
            logger.warning("Unable to purge old backup %s: %s", candidate, exc)
    return removed


def backup_to_drive(retain: int = 7) -> bool:
    """Create a ZIP archive of ``shop.db`` and upload it to Google Drive."""
    if not DB_PATH.exists():
        logger.warning("Google Drive backup skipped: database %s not found", DB_PATH)
        return False

    now_utc = _dt.datetime.now(_dt.timezone.utc)
    archive_path = _build_archive(now_utc)
    logger.info("Backup archive created at %s", archive_path)

    service = _get_drive_service()
    if not service:
        logger.warning("Google Drive backup skipped: Drive client unavailable.")
        removed = purge_old_backups(retain)
        if removed:
            logger.info("Purged %d old backup(s) locally.", len(removed))
        return False

    media = MediaFileUpload(str(archive_path), mimetype="application/zip")  # type: ignore[call-arg]
    metadata = {
        "name": archive_path.name,
        "description": f"ShopApp backup {now_utc:%Y-%m-%d}",
    }

    uploaded = False
    try:
        created = service.files().create(body=metadata, media_body=media, fields="id").execute()
        file_id = created.get("id")
        logger.info("Backup uploaded to Google Drive (id=%s)", file_id)
    except HttpError as exc:  # pragma: no cover - network/Google failure
        logger.exception("Google Drive upload failed: %s", exc)
    except Exception as exc:  # pragma: no cover - unexpected failure
        logger.exception("Unexpected error during Drive backup: %s", exc)
    else:
        uploaded = True
    finally:
        removed = purge_old_backups(retain)
        if removed:
            logger.info("Purged %d old backup(s) locally.", len(removed))

    return uploaded


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="ShopApp Google Drive backup helper.")
    parser.add_argument("command", nargs="?", choices=["purge"], help="only purge local archives without uploading")
    parser.add_argument("--limit", type=int, default=7, help="number of archives to retain (default: 7)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.command == "purge":
        removed = purge_old_backups(limit=args.limit)
        print(f"Purged {len(removed)} archive(s).")
        return 0

    success = backup_to_drive(retain=args.limit)
    if success:
        print("Backup completed successfully.")
        return 0

    print("Backup skipped or failed. See logs for details.")
    return 1


if __name__ == "__main__":
    sys.exit(main())


