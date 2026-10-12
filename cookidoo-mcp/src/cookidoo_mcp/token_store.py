"""Persist the OAuth tokens (never the password) with owner-only permissions."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from cookidoo_api import CookidooAuthData

_LOGGER = logging.getLogger(__name__)


class TokenStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> CookidooAuthData | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return CookidooAuthData(
                access_token=str(data["access_token"]),
                refresh_token=str(data["refresh_token"]),
                expires_at=float(data["expires_at"]),
            )
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, TypeError):
            _LOGGER.warning("Token file %s is unreadable; ignoring it.", self.path)
            return None

    def save(self, auth: CookidooAuthData) -> None:
        """Write atomically so a crash never leaves a half-written token file."""
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = json.dumps(
            {
                "access_token": auth.access_token,
                "refresh_token": auth.refresh_token,
                "expires_at": auth.expires_at,
            }
        )
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".token-")
        try:
            # mkstemp already creates the file 0600 on POSIX; chmod again in
            # case the platform or umask did something unexpected.
            os.chmod(tmp, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def delete(self) -> bool:
        try:
            self.path.unlink()
            return True
        except FileNotFoundError:
            return False
