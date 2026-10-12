from __future__ import annotations

import os
import stat
import sys

import pytest
from cookidoo_api import CookidooAuthData

from cookidoo_mcp.config import load_settings
from cookidoo_mcp.formatting import html_to_text
from cookidoo_mcp.server import _recipe_fields
from cookidoo_mcp.token_store import TokenStore


def test_token_roundtrip_and_permissions(tmp_path):
    store = TokenStore(tmp_path / "sub" / "token.json")
    assert store.load() is None
    store.save(CookidooAuthData(access_token="a", refresh_token="b", expires_at=1.5))
    assert store.load() == CookidooAuthData(access_token="a", refresh_token="b", expires_at=1.5)
    if sys.platform != "win32":
        assert stat.S_IMODE(os.stat(store.path).st_mode) == 0o600
    assert "password" not in store.path.read_text()
    assert store.delete() and not store.path.exists()


def test_corrupt_token_file_is_ignored(tmp_path):
    path = tmp_path / "token.json"
    path.write_text("{not json")
    assert TokenStore(path).load() is None


def test_settings_defaults_and_validation(monkeypatch):
    for var in ("COOKIDOO_COUNTRY", "COOKIDOO_LANGUAGE", "COOKIDOO_READ_ONLY", "COOKIDOO_ALLOW_DELETE"):
        monkeypatch.delenv(var, raising=False)
    s = load_settings()
    assert (s.country, s.language, s.read_only, s.allow_delete) == ("de", "de-DE", False, False)

    monkeypatch.setenv("COOKIDOO_READ_ONLY", "ja")
    assert load_settings().read_only is True

    monkeypatch.setenv("COOKIDOO_COUNTRY", "../x")
    with pytest.raises(ValueError):
        load_settings()


def test_html_to_text():
    assert html_to_text("Mixen <nobr>10 Sek./Stufe&nbsp;5</nobr>.") == "Mixen 10 Sek./Stufe 5."


def test_recipe_fields_only_includes_given_values():
    assert _recipe_fields(
        name=" Brot ", ingredients=None, steps=["  ", "Kneten"], servings=None,
        prep_minutes=10, total_minutes=None, hints=None, thermomix=["TM6", "TM6", "TM7"],
    ) == {
        "name": "Brot",
        "instructions": [{"type": "STEP", "text": "Kneten"}],
        "prepTime": 600,
        "tools": ["TM6", "TM7"],
    }


async def test_service_translates_errors_without_leaking_details(tmp_path):
    from cookidoo_api import CookidooAuthException, CookidooRequestException

    from conftest import FakeService, make_settings
    from cookidoo_mcp.service import CookidooMcpError

    service = FakeService(make_settings(tmp_path), api=object())

    async def auth_fail(_api):
        raise CookidooAuthException("Unexpected token response: {'access_token': 'SECRET'}")

    with pytest.raises(CookidooMcpError) as err:
        await service.run("Loading", auth_fail)
    assert "SECRET" not in str(err.value) and "cookidoo-mcp login" in str(err.value)

    class Resp(Exception):
        status = 404

    async def not_found(_api):
        raise CookidooRequestException("body: SECRET") from Resp()

    with pytest.raises(CookidooMcpError, match="not found") as err:
        await service.run("Loading recipe", not_found)
    assert "SECRET" not in str(err.value)
