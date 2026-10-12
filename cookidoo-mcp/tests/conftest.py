from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from cookidoo_api.types import (
    CookidooAdditionalItem,
    CookidooCalendarDay,
    CookidooCalendarDayRecipe,
    CookidooIngredientItem,
    CookidooShoppingRecipe,
)
from fastmcp import Client

from cookidoo_mcp.config import Settings
from cookidoo_mcp.server import build_server
from cookidoo_mcp.service import CookidooService


def day_recipe(rid: str, name: str = "Rezept") -> CookidooCalendarDayRecipe:
    return CookidooCalendarDayRecipe(id=rid, name=name, total_time=1800, thumbnail=None, image=None, url="")


class FakeApi:
    """Records calls; returns minimal objects shaped like cookidoo-api's."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.calendar: dict[str, CookidooCalendarDay] = {}
        self.shopping_recipes: list[CookidooShoppingRecipe] = []
        self.ingredients = [
            CookidooIngredientItem(id="i1", name="Mehl", is_owned=False, description="200 g"),
            CookidooIngredientItem(id="i2", name="Zucker", is_owned=False, description="50 g"),
        ]
        self.additional = [CookidooAdditionalItem(id="a1", name="Spülmittel", is_owned=False)]

    def _log(self, name: str, *args: Any) -> None:
        self.calls.append((name, args))

    async def get_recipes_in_calendar_week(self, day):
        self._log("get_recipes_in_calendar_week", day)
        # Cookidoo returns the 7 days starting at `day`, omitting empty days.
        from datetime import timedelta

        window = {(day + timedelta(days=i)).isoformat() for i in range(7)}
        return [d for k, d in sorted(self.calendar.items()) if k in window]

    async def get_shopping_list_recipes(self):
        return self.shopping_recipes

    async def add_ingredient_items_for_recipes(self, ids):
        self._log("add_official", list(ids))
        return []

    async def add_ingredient_items_for_custom_recipes(self, ids):
        self._log("add_custom", list(ids))
        return []

    async def get_ingredient_items(self):
        return [replace(i) for i in self.ingredients]

    async def get_additional_items(self):
        return [replace(i) for i in self.additional]

    async def edit_ingredient_items_ownership(self, items):
        self._log("edit_ingredients", [(i.id, i.is_owned) for i in items])
        return items

    async def edit_additional_items_ownership(self, items):
        self._log("edit_additional", [(i.id, i.is_owned) for i in items])
        return items

    async def add_recipes_to_calendar(self, day, ids):
        self._log("plan_official", day, list(ids))
        return CookidooCalendarDay(id=day.isoformat(), title="", recipes=[day_recipe(i) for i in ids])

    async def add_custom_recipes_to_calendar(self, day, ids):
        self._log("plan_custom", day, list(ids))
        return CookidooCalendarDay(
            id=day.isoformat(), title="", recipes=[day_recipe(i) for i in ids], customer_recipe_ids=list(ids)
        )

    async def clear_shopping_list(self):
        self._log("clear")


class FakeService(CookidooService):
    def __init__(self, settings: Settings, api: FakeApi) -> None:
        super().__init__(settings)
        self._fake = api

    async def _connect(self):
        return self._fake


def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    base = dict(
        country="de",
        language="de-DE",
        token_file=tmp_path / "token.json",
        read_only=False,
        allow_delete=False,
        email=None,
        password=None,
    )
    return Settings(**(base | overrides))


@pytest.fixture
def api() -> FakeApi:
    return FakeApi()


@pytest.fixture
def client_for(tmp_path, api):
    def factory(**overrides: Any) -> Client:
        settings = make_settings(tmp_path, **overrides)
        return Client(build_server(settings, FakeService(settings, api)))

    return factory
