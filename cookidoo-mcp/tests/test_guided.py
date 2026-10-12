from __future__ import annotations

import pytest
from pydantic import ValidationError

from cookidoo_mcp.guided import IngredientStep, ModeStep, Phrases, SettingsStep, position, step_to_api

DE = Phrases("de-DE")


def test_positions_match_cookidoo_verified_example():
    # Offsets from the example verified against Cookidoo
    # (vitaliemiron/cookidoo-mcp, examples/guided_recipe.json).
    assert position("Добавьте 75 г сахара.", "75 г сахара") == {"offset": 9, "length": 11}
    assert position("75 г сахара", "75 г") == {"offset": 0, "length": 4}
    text = "Измельчите 30 сек./100°C/обратное вращение/скорость 4."
    assert position(text, "30 сек./100°C/обратное вращение/скорость 4") == {"offset": 11, "length": 42}
    assert position("Замесите тесто 1 мин.", "1 мин.") == {"offset": 15, "length": 6}


def test_positions_count_utf16_units():
    # An emoji is 2 UTF-16 units but 1 Python character.
    assert position("🔥 5 Sek./Stufe 5", "5 Sek./Stufe 5") == {"offset": 3, "length": 14}


def test_settings_step_payload():
    step = SettingsStep(kind="settings", text="Zwiebel {settings} zerkleinern.", time_seconds=5, speed="5")
    out = step_to_api(step, DE)
    assert out["text"] == "Zwiebel 5 Sek./Stufe 5 zerkleinern."
    (ann,) = out["annotations"]
    assert ann == {"type": "TTS", "data": {"speed": "5", "time": 5}, "position": {"offset": 8, "length": 14}}


def test_settings_with_heat_and_reverse():
    step = SettingsStep(kind="settings", text="Dünsten.", time_seconds=180, speed="1", temperature_c=120, reverse=True)
    out = step_to_api(step, DE)
    assert out["text"] == "Dünsten. 3 Min./120°C/Linkslauf/Stufe 1"
    data = out["annotations"][0]["data"]
    assert data == {"speed": "1", "time": 180, "direction": "CCW", "temperature": {"value": "120", "unit": "C"}}


def test_soft_speed_and_decimal_speed_phrases():
    assert DE.speed("soft") == "Sanftrührstufe"
    assert DE.speed("2.5") == "Stufe 2,5"
    assert DE.time(90) == "1 Min. 30 Sek."
    assert Phrases("en").settings(SettingsStep(kind="settings", time_seconds=30, speed="4")) == "30 sec/speed 4"


def test_ingredient_step_payload():
    out = step_to_api(IngredientStep(kind="ingredient", ingredient="200 g Mehl"), DE)
    assert out["text"] == "200 g Mehl in den Mixtopf geben."
    (ann,) = out["annotations"]
    assert ann["type"] == "INGREDIENT"
    assert ann["position"] == {"offset": 0, "length": 10}
    assert ann["data"]["description"] == {
        "text": "200 g Mehl",
        "annotations": [{"type": "VOLUME", "data": {"amount": 200.0, "unit": "gram", "unitText": "g"},
                         "position": {"offset": 0, "length": 5}}],
    }


def test_ingredient_step_without_grams_is_rejected():
    with pytest.raises(ValueError, match="grams"):
        step_to_api(IngredientStep(kind="ingredient", ingredient="1 Zwiebel"), DE)


def test_mode_payloads_and_rules():
    out = step_to_api(ModeStep(kind="mode", mode="DOUGH", text="Den Teig {settings} lang kneten.", time_seconds=120), DE)
    assert out["text"] == "Den Teig Teig kneten 2 Min. lang kneten."
    ann = out["annotations"][0]
    assert (ann["type"], ann["name"], ann["data"]) == ("MODE", "DOUGH", {"time": 120})

    steam = step_to_api(
        ModeStep(kind="mode", mode="STEAMING", time_seconds=1200, speed="1", accessory="Varoma"), DE
    )
    assert steam["annotations"][0]["data"] == {"time": 1200, "speed": "1", "direction": "CW", "accessory": "Varoma"}

    with pytest.raises(ValidationError, match="TURBO"):
        ModeStep(kind="mode", mode="TURBO", time_seconds=5)
    with pytest.raises(ValidationError, match="needs"):
        ModeStep(kind="mode", mode="BLEND", time_seconds=60)
    with pytest.raises(ValidationError, match="speed 6"):
        SettingsStep(kind="settings", time_seconds=10, speed="8", temperature_c=100)
