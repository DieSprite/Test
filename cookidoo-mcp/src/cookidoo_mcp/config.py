"""Configuration from environment variables.

Nothing here is read from files in the working directory: a stray ``.env`` in
whatever folder the MCP client starts the server from must not be able to
change where tokens are stored or which account is used.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "cookidoo-mcp"
DEFAULT_COUNTRY = "de"
DEFAULT_LANGUAGE = "de-DE"

_TRUE = {"1", "true", "yes", "on", "ja"}


def default_config_dir() -> Path:
    """Per-user config directory, following each platform's convention."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_NAME


@dataclass(frozen=True)
class Settings:
    country: str
    language: str
    token_file: Path
    read_only: bool
    allow_delete: bool
    # Optional fallback for unattended re-login. Not needed when the token
    # from `cookidoo-mcp login` is used, which is the recommended setup.
    email: str | None
    password: str | None

    @property
    def has_password_login(self) -> bool:
        return bool(self.email and self.password)


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUE


def load_settings() -> Settings:
    country = os.environ.get("COOKIDOO_COUNTRY", DEFAULT_COUNTRY).strip().lower()
    if not re.fullmatch(r"[a-z]{2}", country):
        raise ValueError("COOKIDOO_COUNTRY must be a two-letter code such as 'de'.")
    language = os.environ.get("COOKIDOO_LANGUAGE", DEFAULT_LANGUAGE).strip()
    if not re.fullmatch(r"[a-z]{2}(-[A-Z]{2})?", language):
        raise ValueError("COOKIDOO_LANGUAGE must look like 'de-DE' or 'en'.")

    token_file = os.environ.get("COOKIDOO_TOKEN_FILE")
    return Settings(
        country=country,
        language=language,
        token_file=Path(token_file).expanduser()
        if token_file
        else default_config_dir() / "token.json",
        read_only=_flag("COOKIDOO_READ_ONLY"),
        allow_delete=_flag("COOKIDOO_ALLOW_DELETE"),
        email=os.environ.get("COOKIDOO_EMAIL") or None,
        password=os.environ.get("COOKIDOO_PASSWORD") or None,
    )
