"""Command line: `cookidoo-mcp [serve|login|logout|status]`."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import logging
import os
import sys

from cookidoo_api import CookidooAuthException, CookidooException

from cookidoo_mcp import __version__
from cookidoo_mcp.config import load_settings
from cookidoo_mcp.service import CookidooMcpError, password_login
from cookidoo_mcp.token_store import TokenStore


def _login(args: argparse.Namespace) -> int:
    settings = load_settings()
    store = TokenStore(settings.token_file)
    email = args.email or os.environ.get("COOKIDOO_EMAIL") or input("Cookidoo E-Mail: ").strip()
    password = getpass.getpass("Cookidoo Passwort (wird nicht gespeichert): ")
    try:
        asyncio.run(password_login(settings, email, password, store))
    except CookidooAuthException:
        print("Anmeldung fehlgeschlagen: E-Mail oder Passwort falsch.", file=sys.stderr)
        return 1
    except (CookidooException, CookidooMcpError) as e:
        print(f"Anmeldung fehlgeschlagen: {e}", file=sys.stderr)
        return 1
    print(f"Angemeldet ({settings.country}/{settings.language}). Token gespeichert in:")
    print(f"  {store.path}")
    print("Das Passwort wurde nicht gespeichert.")
    return 0


def _logout(_args: argparse.Namespace) -> int:
    store = TokenStore(load_settings().token_file)
    print("Token gelöscht." if store.delete() else "Es war kein Token gespeichert.")
    return 0


def _status(_args: argparse.Namespace) -> int:
    s = load_settings()
    has_token = TokenStore(s.token_file).load() is not None
    print(f"Version:        {__version__}")
    print(f"Land/Sprache:   {s.country} / {s.language}")
    print(f"Token-Datei:    {s.token_file} ({'vorhanden' if has_token else 'fehlt'})")
    print(f"Passwort-Login: {'ja (COOKIDOO_PASSWORD gesetzt)' if s.has_password_login else 'nein'}")
    mode = "nur lesen" if s.read_only else ("lesen, schreiben, löschen" if s.allow_delete else "lesen, schreiben")
    print(f"Modus:          {mode}")
    return 0


def _serve(_args: argparse.Namespace) -> int:
    from cookidoo_mcp.server import build_server

    build_server(load_settings()).run(show_banner=False)
    return 0


def main() -> None:
    # stdout carries the MCP protocol; all logging goes to stderr.
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(prog="cookidoo-mcp", description="MCP server for Thermomix Cookidoo")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="Start the MCP server on stdio (default)")
    login = sub.add_parser("login", help="Log in once and store the token (not the password)")
    login.add_argument("--email")
    sub.add_parser("logout", help="Delete the stored token")
    sub.add_parser("status", help="Show configuration")
    args = parser.parse_args()

    handler = {"login": _login, "logout": _logout, "status": _status}.get(args.command, _serve)
    try:
        sys.exit(handler(args))
    except ValueError as e:  # bad COOKIDOO_* settings
        print(f"Konfigurationsfehler: {e}", file=sys.stderr)
        sys.exit(2)
