"""Turn cookidoo-api objects into compact, model-friendly dicts."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import Any

from cookidoo_api.types import (
    CookidooAdditionalItem,
    CookidooCalendarDay,
    CookidooCollection,
    CookidooCustomRecipe,
    CookidooIngredientItem,
    CookidooSearchRecipeHit,
    CookidooShoppingRecipe,
    CookidooShoppingRecipeDetails,
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(markup: str) -> str:
    """Strip tags from Cookidoo's step HTML (e.g. <nobr>10 Sek./Stufe 5</nobr>)."""
    parser = _TextExtractor()
    parser.feed(markup)
    parser.close()
    return re.sub(r"\s+", " ", html.unescape("".join(parser.parts))).strip()


def minutes(seconds: int | float | str | None) -> int | None:
    # The calendar endpoint returns times as strings like "19200.0".
    try:
        value = float(seconds) if seconds is not None else 0.0
    except (TypeError, ValueError):
        return None
    return round(value / 60) if value else None


def search_hit(hit: CookidooSearchRecipeHit) -> dict[str, Any]:
    return {"id": hit.id, "name": hit.name, "url": hit.url}


def recipe_details(r: CookidooShoppingRecipeDetails) -> dict[str, Any]:
    nutrition = []
    for group in r.nutrition_groups:
        for rn in group.recipe_nutritions:
            nutrition.append(
                {
                    "per": f"{rn.quantity} {rn.unit_notation}".strip(),
                    "values": {n.type: f"{n.number:g} {n.unittype}" for n in rn.nutritions},
                }
            )
    return {
        "id": r.id,
        "name": r.name,
        "url": r.url,
        "difficulty": r.difficulty,
        "servings": r.serving_size,
        "active_minutes": minutes(r.active_time),
        "total_minutes": minutes(r.total_time),
        "ingredients": [
            f"{i.description} {i.name}".strip() if i.description else i.name
            for i in r.ingredients
        ],
        "steps": [
            {
                "section": g.title or None,
                "steps": [html_to_text(s.formatted_text) for s in g.recipe_steps],
            }
            for g in r.step_groups
        ],
        "utensils": r.utensils,
        "notes": [html_to_text(n) for n in r.notes],
        "categories": [c.name for c in r.categories],
        "nutrition": nutrition,
    }


def custom_recipe(r: CookidooCustomRecipe, full: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": r.id,
        "name": r.name,
        "url": r.url,
        "servings": r.serving_size,
        "total_minutes": minutes(r.total_time),
    }
    if full:
        out |= {
            "active_minutes": minutes(r.active_time),
            "ingredients": r.ingredients,
            "steps": [html_to_text(s) for s in r.instructions],
            "thermomix": r.tools,
        }
    return out


def ingredient_item(i: CookidooIngredientItem) -> dict[str, Any]:
    return {"id": i.id, "name": i.name, "amount": i.description, "owned": i.is_owned}


def additional_item(i: CookidooAdditionalItem) -> dict[str, Any]:
    return {"id": i.id, "name": i.name, "owned": i.is_owned}


def shopping_recipe(r: CookidooShoppingRecipe) -> dict[str, Any]:
    return {"id": r.id, "name": r.name}


def calendar_day(d: CookidooCalendarDay) -> dict[str, Any]:
    custom = set(d.customer_recipe_ids)
    return {
        "date": d.id,
        "recipes": [
            {
                "id": r.id,
                "name": r.name,
                "total_minutes": minutes(r.total_time),
                "custom": r.id in custom,
            }
            for r in d.recipes
        ]
        + [{"id": cid, "custom": True} for cid in custom - {r.id for r in d.recipes}],
    }


def collection(c: CookidooCollection) -> dict[str, Any]:
    recipes = [
        {"id": r.id, "name": r.name} for chapter in c.chapters for r in chapter.recipes
    ]
    return {"id": c.id, "name": c.name, "recipe_count": len(recipes), "recipes": recipes}
