from __future__ import annotations

from datetime import date

import pytest
from cookidoo_api.types import CookidooCalendarDay, CookidooShoppingRecipe
from fastmcp.exceptions import ToolError

from conftest import day_recipe

READ_TOOLS = {
    "account_info", "search_recipes", "get_recipe", "list_custom_recipes",
    "get_custom_recipe", "get_shopping_list", "get_meal_plan", "list_collections",
    "preview_custom_recipe",
}
DELETE_TOOLS = {"clear_shopping_list", "delete_custom_recipe", "delete_collection"}


async def tool_names(client) -> set[str]:
    async with client:
        return {t.name for t in await client.list_tools()}


async def test_default_mode_has_no_delete_tools(client_for):
    names = await tool_names(client_for())
    assert READ_TOOLS <= names
    assert "add_recipes_to_shopping_list" in names
    assert not names & DELETE_TOOLS


async def test_read_only_mode_exposes_only_read_tools(client_for):
    assert await tool_names(client_for(read_only=True)) == READ_TOOLS


async def test_read_only_wins_over_allow_delete(client_for):
    assert await tool_names(client_for(read_only=True, allow_delete=True)) == READ_TOOLS


async def test_delete_tools_need_flag_and_confirm(client_for, api):
    client = client_for(allow_delete=True)
    async with client:
        names = {t.name for t in await client.list_tools()}
        assert DELETE_TOOLS <= names
        with pytest.raises(ToolError, match="confirm=true"):
            await client.call_tool("clear_shopping_list", {})
        assert ("clear", ()) not in api.calls
        await client.call_tool("clear_shopping_list", {"confirm": True})
        assert ("clear", ()) in api.calls


async def test_annotations(client_for):
    async with client_for(allow_delete=True) as client:
        tools = {t.name: t for t in await client.list_tools()}
    assert tools["get_shopping_list"].annotations.read_only_hint is True
    assert tools["add_shopping_items"].annotations.destructive_hint is False
    assert tools["remove_shopping_items"].annotations.destructive_hint is True
    assert tools["clear_shopping_list"].annotations.destructive_hint is True


@pytest.mark.parametrize("bad", ["../../profile", "r1/../x", "a b", "", "x" * 81, "r1?x=1"])
async def test_ids_are_validated_before_any_request(client_for, api, bad):
    async with client_for() as client:
        with pytest.raises(ToolError, match="Invalid"):
            await client.call_tool("add_recipes_to_shopping_list", {"recipe_ids": [bad]})
    assert api.calls == []


async def test_official_and_custom_ids_are_routed_separately(client_for, api):
    async with client_for() as client:
        await client.call_tool("add_recipes_to_shopping_list", {"recipe_ids": ["r123", "01ABCdef", "r123"]})
    assert ("add_official", (["r123"],)) in api.calls
    assert ("add_custom", (["01ABCdef"],)) in api.calls


async def test_meal_plan_to_shopping_list_skips_existing_and_respects_range(client_for, api):
    api.calendar = {
        "2026-10-12": CookidooCalendarDay(id="2026-10-12", title="", recipes=[day_recipe("r1"), day_recipe("r2")]),
        "2026-10-14": CookidooCalendarDay(
            id="2026-10-14", title="", recipes=[day_recipe("c9")], customer_recipe_ids=["c9"]
        ),
        "2026-10-20": CookidooCalendarDay(id="2026-10-20", title="", recipes=[day_recipe("r3")]),
        "2026-10-25": CookidooCalendarDay(id="2026-10-25", title="", recipes=[day_recipe("r4")]),
    }
    api.shopping_recipes = [CookidooShoppingRecipe(id="r2", name="", ingredients=[], thumbnail=None, image=None, url="")]
    async with client_for() as client:
        res = await client.call_tool("add_meal_plan_to_shopping_list", {"start": "2026-10-12", "days": 9})
    data = res.structured_content
    assert data["to"] == "2026-10-20"
    assert sorted(data["added_recipes"]) == ["c9", "r1", "r3"]
    assert data["already_on_list"] == ["r2"]
    assert ("add_official", (["r1", "r3"],)) in api.calls
    assert ("add_custom", (["c9"],)) in api.calls


async def test_set_owned_reports_unknown_ids(client_for, api):
    async with client_for() as client:
        res = await client.call_tool("set_shopping_items_owned", {"item_ids": ["i2", "a1", "zz"]})
    assert ("edit_ingredients", ([("i2", True)],)) in api.calls
    assert ("edit_additional", ([("a1", True)],)) in api.calls
    assert res.structured_content["not_found"] == ["zz"]


async def test_plan_custom_recipe(client_for, api):
    async with client_for() as client:
        res = await client.call_tool("plan_recipes", {"day": "2026-10-13", "recipe_ids": ["myrecipe1"]})
    assert ("plan_custom", (date(2026, 10, 13), ["myrecipe1"])) in api.calls
    assert res.structured_content["recipes"][0]["custom"] is True


async def test_official_recipe_cannot_be_edited(client_for, api):
    async with client_for() as client:
        with pytest.raises(ToolError, match="copy_recipe_to_custom"):
            await client.call_tool("update_custom_recipe", {"recipe_id": "r123", "name": "x"})


async def test_not_logged_in_message(tmp_path):
    from fastmcp import Client

    from conftest import make_settings
    from cookidoo_mcp.server import build_server

    async with Client(build_server(make_settings(tmp_path))) as client:
        with pytest.raises(ToolError, match="cookidoo-mcp login"):
            await client.call_tool("get_shopping_list", {})


async def test_preview_and_create_send_guided_annotations(client_for, api):
    steps = [
        "Zwiebel halbieren.",
        {"kind": "ingredient", "ingredient": "200 g Mehl"},
        {"kind": "settings", "text": "{settings} vermischen.", "time_seconds": 20, "speed": "4"},
        {"kind": "mode", "mode": "DOUGH", "time_seconds": 120},
    ]
    async with client_for() as client:
        prev = (await client.call_tool("preview_custom_recipe", {"steps": steps})).structured_content
        assert [s["text"] for s in prev["steps"]] == [
            "Zwiebel halbieren.",
            "200 g Mehl in den Mixtopf geben.",
            "20 Sek./Stufe 4 vermischen.",
            "Teig kneten 2 Min.",
        ]
        assert prev["steps"][1]["guided"] == {"type": "weigh", "marked": "200 g Mehl", "grams": 200.0}
        assert prev["steps"][2]["guided"]["marked"] == "20 Sek./Stufe 4"

        with pytest.raises(ToolError, match="grams"):
            await client.call_tool("preview_custom_recipe", {"steps": [{"kind": "ingredient", "ingredient": "1 Ei"}]})


async def test_create_custom_recipe_patches_guided_steps(client_for, api, monkeypatch):
    from cookidoo_api.types import CookidooCustomRecipe

    from cookidoo_mcp.service import CookidooService

    sent = {}

    async def fake_create(_api, name):
        sent["name"] = name
        return "new1"

    async def fake_patch(_api, rid, fields):
        sent["patch"] = (rid, fields)

    async def fake_get(rid):
        return CookidooCustomRecipe(id=rid, name="Brot", ingredients=[], instructions=[], tools=["TM6"],
                                    serving_size=2, active_time=0, total_time=0, thumbnail=None, image=None, url="")

    monkeypatch.setattr(CookidooService, "create_custom_recipe", staticmethod(fake_create))
    monkeypatch.setattr(CookidooService, "patch_custom_recipe", staticmethod(fake_patch))
    api.get_custom_recipe = fake_get
    async with client_for() as client:
        await client.call_tool("create_custom_recipe", {
            "name": "Brot", "ingredients": ["500 g Mehl"],
            "steps": [{"kind": "settings", "time_seconds": 10, "speed": "6"}],
        })
    rid, fields = sent["patch"]
    assert rid == "new1"
    assert fields["instructions"] == [{
        "type": "STEP", "text": "10 Sek./Stufe 6",
        "annotations": [{"type": "TTS", "data": {"speed": "6", "time": 10}, "position": {"offset": 0, "length": 15}}],
    }]
    assert fields["ingredients"] == [{"type": "INGREDIENT", "text": "500 g Mehl"}]
    assert fields["workStatus"] == "PRIVATE"
