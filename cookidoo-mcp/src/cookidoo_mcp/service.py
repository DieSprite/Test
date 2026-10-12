"""Connection handling around cookidoo-api.

Security choices made here:

* TLS certificates are always verified (aiohttp's default; never disabled).
* The password is only needed once, for ``cookidoo-mcp login``. The server
  then runs on the stored OAuth tokens and saves the rotated ones itself.
* Error messages handed to the model never contain response bodies or tokens.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import aiohttp
from cookidoo_api import (
    Cookidoo,
    CookidooAuthException,
    CookidooConfig,
    CookidooException,
    CookidooRequestException,
    get_localization_options,
)
from cookidoo_api.types import CookidooLocalizationConfig

from cookidoo_mcp.config import Settings
from cookidoo_mcp.token_store import TokenStore

_LOGGER = logging.getLogger(__name__)
_T = TypeVar("_T")

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class CookidooMcpError(Exception):
    """An error whose message is safe to show to the model and the user."""


NOT_LOGGED_IN = (
    "Not logged in to Cookidoo. Run `cookidoo-mcp login` once in a terminal, "
    "then restart the MCP client."
)


async def resolve_localization(country: str, language: str) -> CookidooLocalizationConfig:
    options = await get_localization_options(country=country, language=language)
    if not options:
        raise CookidooMcpError(
            f"Cookidoo has no localization for country '{country}' and language "
            f"'{language}'. For Germany use COOKIDOO_COUNTRY=de, COOKIDOO_LANGUAGE=de-DE."
        )
    return options[0]


def new_http_session() -> aiohttp.ClientSession:
    # cookie_jar(unsafe=True) is required by cookidoo-api for the cross-domain
    # OAuth redirects. TLS verification stays at aiohttp's secure default.
    return aiohttp.ClientSession(
        cookie_jar=aiohttp.CookieJar(unsafe=True), timeout=REQUEST_TIMEOUT
    )


async def password_login(
    settings: Settings, email: str, password: str, store: TokenStore
) -> None:
    """Log in once with email and password and persist only the tokens."""
    localization = await resolve_localization(settings.country, settings.language)
    async with new_http_session() as session:
        api = Cookidoo(
            session,
            CookidooConfig(localization=localization, email=email, password=password),
            on_auth_data_update=store.save,
        )
        await api.login()
        # Fail now rather than on the first tool call if the token is unusable.
        await api.get_user_info()


class CookidooService:
    """Lazily connected, shared Cookidoo client for all tool calls."""

    def __init__(self, settings: Settings, store: TokenStore | None = None) -> None:
        self.settings = settings
        self.store = store or TokenStore(settings.token_file)
        self._session: aiohttp.ClientSession | None = None
        self._api: Cookidoo | None = None
        self._lock = asyncio.Lock()

    async def _connect(self) -> Cookidoo:
        async with self._lock:
            if self._api is not None:
                return self._api
            localization = await resolve_localization(
                self.settings.country, self.settings.language
            )
            session = new_http_session()
            api = Cookidoo(
                session,
                CookidooConfig(
                    localization=localization,
                    email=self.settings.email or "",
                    password=self.settings.password or "",
                ),
                on_auth_data_update=self.store.save,
            )
            try:
                if (auth := self.store.load()) is not None:
                    api.apply_auth_data(auth)
                elif self.settings.has_password_login:
                    await api.login()
                else:
                    raise CookidooMcpError(NOT_LOGGED_IN)
            except BaseException:
                await session.close()
                raise
            self._session, self._api = session, api
            return api

    async def _relogin(self) -> bool:
        """Recover from a rejected token with the optional password fallback."""
        if self._api is None or not self.settings.has_password_login:
            return False
        try:
            await self._api.login()
        except CookidooException:
            _LOGGER.warning("Re-login with COOKIDOO_EMAIL/COOKIDOO_PASSWORD failed.")
            return False
        return True

    async def run(self, operation: str, fn: Callable[[Cookidoo], Awaitable[_T]]) -> _T:
        """Run ``fn`` against the API and translate errors into safe messages."""
        try:
            api = await self._connect()
            try:
                return await fn(api)
            except CookidooAuthException:
                if not await self._relogin():
                    raise
                return await fn(api)
        except CookidooMcpError:
            raise
        except CookidooAuthException as e:
            _LOGGER.warning("Authorization failed during %s.", operation)
            raise CookidooMcpError(
                "Cookidoo rejected the stored login (it may have expired). "
                "Run `cookidoo-mcp login` again, then restart the MCP client."
            ) from e
        except CookidooRequestException as e:
            # Includes HTTP 404 (wrong ID) and network problems.
            _LOGGER.warning("Request failed during %s: %s", operation, e.__cause__ or e)
            status = getattr(e.__cause__, "status", None)
            if status == 404:
                raise CookidooMcpError(
                    f"{operation}: not found. Check the ID (official recipes look like 'r59322')."
                ) from e
            raise CookidooMcpError(
                f"{operation} failed"
                + (f" (HTTP {status})." if status else " (network problem).")
            ) from e
        except CookidooException as e:
            _LOGGER.warning("Cookidoo error during %s: %s", operation, type(e).__name__)
            raise CookidooMcpError(
                f"{operation} failed: Cookidoo returned an unexpected response."
            ) from e

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
        self._session = self._api = None

    # -- custom recipe editor ------------------------------------------------
    # cookidoo-api can copy and delete custom recipes but not create or edit
    # them, so these two calls use the endpoint of Cookidoo's own web editor.
    # They go through the library's request helper so token refresh, TLS and
    # error handling stay identical to every other call.

    @staticmethod
    async def _created_recipes_url(api: Cookidoo, recipe_id: str | None = None):
        await api._ensure_endpoints()
        loc = api.localization.__dict__
        if recipe_id is None:
            return api.api_endpoint / api._path("customer-recipes:recipe-create").format(**loc)
        return api.api_endpoint / api._path("customer-recipes:recipe-details").format(
            **loc, id=recipe_id
        )

    @classmethod
    async def create_custom_recipe(cls, api: Cookidoo, name: str) -> str:
        url = await cls._created_recipes_url(api)
        result = await api._request_json(
            "post", url, "create custom recipe", json={"recipeName": name}
        )
        recipe_id = result.get("recipeId") if isinstance(result, dict) else None
        if not isinstance(recipe_id, str) or not recipe_id:
            raise CookidooMcpError("Cookidoo did not return an ID for the new recipe.")
        return recipe_id

    @classmethod
    async def patch_custom_recipe(
        cls, api: Cookidoo, recipe_id: str, fields: dict[str, Any]
    ) -> None:
        url = await cls._created_recipes_url(api, recipe_id)
        # A freshly created recipe is not always editable immediately; retry
        # briefly instead of sleeping a fixed time on every call.
        for delay in (0, 1, 2, 4):
            if delay:
                await asyncio.sleep(delay)
            try:
                await api._request_json(
                    "patch",
                    url,
                    "update custom recipe",
                    json=fields,
                    headers={"Content-Type": "application/json"},
                    parse_response=False,
                )
                return
            except CookidooRequestException as e:
                status = getattr(e.__cause__, "status", None)
                if status not in (404, 409) or delay == 4:
                    raise
