"""Guided cooking for custom recipes.

Cookidoo's recipe editor stores machine settings as *annotations*: a typed
object plus a character range pointing at the readable phrase in the step
text (e.g. "5 Sek./Stufe 5"). The range is measured in JavaScript UTF-16 code
units. The annotation format follows the example verified against Cookidoo in
https://github.com/vitaliemiron/cookidoo-mcp (Apache-2.0, examples/guided_recipe.json).

Instead of making the model compute offsets, the tools accept high-level step
objects; this module writes the settings phrase into the text and computes
every range itself.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Speed = Literal[
    "soft", "0.5", "1", "1.5", "2", "2.5", "3", "3.5", "4", "4.5", "5",
    "5.5", "6", "6.5", "7", "7.5", "8", "8.5", "9", "9.5", "10",
]

SETTINGS = "{settings}"
INGREDIENT = "{ingredient}"

# "200 g", "1,5 kg" is not weighed: only grams map to the scale reliably.
_GRAMS = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)?)(?:\s*[-–]\s*(\d+(?:[.,]\d+)?))?\s*(?:g|Gramm|gram|grams)\b")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- step input


class TextStep(_Model):
    kind: Literal["text"] = "text"
    text: str = Field(min_length=1, max_length=1000)


class IngredientStep(_Model):
    """Add/weigh one ingredient; the Thermomix scale shows the target amount."""

    kind: Literal["ingredient"]
    ingredient: str = Field(
        min_length=1, max_length=200, description="Phrase with amount in grams, e.g. '200 g Mehl'."
    )
    text: str = Field(
        default="{ingredient} in den Mixtopf geben.",
        max_length=1000,
        description="Step text containing '{ingredient}' or the ingredient phrase itself.",
    )


class SettingsStep(_Model):
    """Manual machine settings: time, optional temperature, speed, reverse."""

    kind: Literal["settings"]
    text: str = Field(
        default="{settings}",
        max_length=1000,
        description="Step text; '{settings}' is replaced by e.g. '5 Sek./Stufe 5'. Appended if missing.",
    )
    time_seconds: int = Field(ge=1, le=5940)
    speed: Speed
    temperature_c: int | None = Field(default=None, ge=37, le=120)
    reverse: bool = Field(default=False, description="Linkslauf (counter-clockwise).")

    @model_validator(mode="after")
    def _check(self) -> SettingsStep:
        if self.temperature_c is not None and self.speed != "soft" and float(self.speed) > 6:
            raise ValueError("Thermomix cannot heat above speed 6.")
        return self


class ModeStep(_Model):
    """A Thermomix smart mode (TM6/TM7)."""

    kind: Literal["mode"]
    mode: Literal["DOUGH", "TURBO", "BLEND", "WARM_UP", "STEAMING", "BROWNING", "RICE_COOKER"]
    text: str = Field(default="{settings}", max_length=1000)
    time_seconds: float | None = Field(default=None, gt=0, le=5940)
    speed: Speed | None = None
    temperature_c: int | None = Field(default=None, ge=37, le=160)
    reverse: bool = False
    pulse_count: int | None = Field(default=None, ge=1, le=20, description="TURBO only.")
    accessory: Literal["Varoma", "SimmeringBasket", "VaromaAndSimmeringBasket"] | None = None
    power: Literal["Gentle", "Intense"] | None = Field(default=None, description="BROWNING only.")

    @model_validator(mode="after")
    def _check(self) -> ModeStep:
        given = {k for k in ("time_seconds", "speed", "temperature_c", "pulse_count", "accessory", "power")
                 if getattr(self, k) is not None}
        required, allowed = {
            "DOUGH": ({"time_seconds"}, {"time_seconds"}),
            "TURBO": ({"time_seconds"}, {"time_seconds", "pulse_count"}),
            "BLEND": ({"time_seconds", "speed"}, {"time_seconds", "speed"}),
            "WARM_UP": ({"temperature_c", "speed"}, {"temperature_c", "speed"}),
            "STEAMING": ({"time_seconds", "speed", "accessory"}, {"time_seconds", "speed", "accessory"}),
            "BROWNING": ({"time_seconds", "temperature_c", "power"}, {"time_seconds", "temperature_c", "power"}),
            "RICE_COOKER": (set(), set()),
        }[self.mode]
        if missing := required - given:
            raise ValueError(f"{self.mode} needs: {', '.join(sorted(missing))}")
        if extra := given - allowed:
            raise ValueError(f"{self.mode} does not take: {', '.join(sorted(extra))}")
        t, s = self.time_seconds, self.speed
        if self.mode == "DOUGH" and t > 1200:
            raise ValueError("DOUGH: at most 1200 seconds.")
        if self.mode == "TURBO" and t not in (0.5, 1, 2):
            raise ValueError("TURBO: time must be 0.5, 1 or 2 seconds.")
        if self.mode == "BLEND" and (not 10 <= t <= 300 or s not in {"6", "6.5", "7", "7.5", "8"}):
            raise ValueError("BLEND: 10-300 seconds at speed 6-8.")
        if self.mode == "WARM_UP" and s not in {"soft", "1", "2"}:
            raise ValueError("WARM_UP: speed soft, 1 or 2.")
        if self.mode == "BROWNING" and t > 1800:
            raise ValueError("BROWNING: at most 1800 seconds.")
        if self.reverse and self.mode != "STEAMING":
            raise ValueError("reverse is only supported for STEAMING here; use a settings step otherwise.")
        return self


GuidedStep = Annotated[TextStep | IngredientStep | SettingsStep | ModeStep, Field(discriminator="kind")]
StepInput = str | GuidedStep


class IngredientInput(_Model):
    text: str = Field(min_length=1, max_length=200, description="e.g. '200 g Mehl'")


# ---------------------------------------------------------------- text helpers


def utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def position(text: str, phrase: str) -> dict[str, int]:
    """UTF-16 range of the first occurrence of `phrase` in `text`."""
    start = text.find(phrase)
    if start < 0 or not phrase.strip():
        raise ValueError(f"'{phrase}' does not appear in step text '{text}'.")
    return {"offset": utf16_len(text[:start]), "length": utf16_len(phrase)}


def _num(value: float) -> str:
    return f"{value:g}"


def _amount(raw: str) -> float:
    return float(raw.replace(",", "."))


class Phrases:
    """Display phrases in Cookidoo's notation for the account language."""

    def __init__(self, language: str) -> None:
        self.de = language.lower().startswith("de")

    def time(self, seconds: float) -> str:
        sec, mn = ("Sek.", "Min.") if self.de else ("sec", "min")
        if seconds < 60 or seconds != int(seconds):
            return f"{_num(seconds)} {sec}"
        m, s = divmod(int(seconds), 60)
        return f"{m} {mn}" + (f" {s} {sec}" if s else "")

    def speed(self, speed: str) -> str:
        if speed == "soft":
            return "Sanftrührstufe" if self.de else "speed soft"
        return f"Stufe {speed.replace('.', ',')}" if self.de else f"speed {speed}"

    def reverse(self) -> str:
        return "Linkslauf" if self.de else "reverse"

    def settings(self, s: SettingsStep) -> str:
        parts = [self.time(s.time_seconds)]
        if s.temperature_c is not None:
            parts.append(f"{s.temperature_c}°C")
        if s.reverse:
            parts.append(self.reverse())
        parts.append(self.speed(s.speed))
        return "/".join(parts)

    def mode(self, m: ModeStep) -> str:
        names_de = {"DOUGH": "Teig kneten", "TURBO": "Turbo", "BLEND": "Mixen", "WARM_UP": "Aufwärmen",
                    "STEAMING": "Dampfgaren", "BROWNING": "Anbraten", "RICE_COOKER": "Reis kochen"}
        names_en = {"DOUGH": "Dough", "TURBO": "Turbo", "BLEND": "Blend", "WARM_UP": "Warm up",
                    "STEAMING": "Steaming", "BROWNING": "Browning", "RICE_COOKER": "Rice cooker"}
        parts = []
        if m.time_seconds is not None:
            parts.append(self.time(m.time_seconds))
        if m.pulse_count:
            parts.append(f"{m.pulse_count}x")
        if m.temperature_c is not None:
            parts.append(f"{m.temperature_c}°C")
        if m.accessory:
            parts.append({"SimmeringBasket": "Garkörbchen" if self.de else "simmering basket",
                          "VaromaAndSimmeringBasket": "Varoma + Garkörbchen" if self.de else "Varoma + basket"}
                         .get(m.accessory, "Varoma"))
        if m.reverse:
            parts.append(self.reverse())
        if m.speed is not None:
            parts.append(self.speed(m.speed))
        if m.power:
            parts.append({"Gentle": "sanft", "Intense": "intensiv"}[m.power] if self.de else m.power.lower())
        label = (names_de if self.de else names_en)[m.mode]
        return f"{label} {'/'.join(parts)}".strip()


def _insert(template: str, placeholder: str, phrase: str) -> str:
    if placeholder in template:
        return template.replace(placeholder, phrase, 1)
    if phrase in template:
        return template
    return f"{template.rstrip()} {phrase}".strip()


# ---------------------------------------------------------------- API payloads


def volume_annotation(text: str) -> dict[str, Any] | None:
    """VOLUME annotation for the first gram amount in `text`, if any."""
    match = _GRAMS.search(text)
    if not match:
        return None
    data: dict[str, Any] = {"amount": _amount(match.group(1)), "unit": "gram", "unitText": "g"}
    if match.group(2):
        data["amountMax"] = _amount(match.group(2))
    phrase = match.group(0)
    return {"type": "VOLUME", "data": data, "position": position(text, phrase)}


def ingredient_to_api(item: str | IngredientInput) -> dict[str, Any]:
    text = (item.text if isinstance(item, IngredientInput) else item).strip()
    out: dict[str, Any] = {"type": "INGREDIENT", "text": text}
    if vol := volume_annotation(text):
        out["annotations"] = [vol]
    return out


def step_to_api(step: StepInput, phrases: Phrases) -> dict[str, Any]:
    if isinstance(step, str):
        step = TextStep(text=step)

    if isinstance(step, TextStep):
        return {"type": "STEP", "text": step.text.strip()}

    if isinstance(step, IngredientStep):
        phrase = step.ingredient.strip()
        vol = volume_annotation(phrase)
        if vol is None:
            raise ValueError(
                f"Ingredient step '{phrase}' needs an amount in grams (e.g. '200 g Mehl') for the scale; "
                "use a plain text step otherwise."
            )
        text = _insert(step.text.strip(), INGREDIENT, phrase)
        return {
            "type": "STEP",
            "text": text,
            "annotations": [{
                "type": "INGREDIENT",
                "data": {"description": {"text": phrase, "annotations": [vol]}},
                "position": position(text, phrase),
            }],
        }

    if isinstance(step, SettingsStep):
        phrase = phrases.settings(step)
        text = _insert(step.text.strip(), SETTINGS, phrase)
        data: dict[str, Any] = {"speed": step.speed, "time": step.time_seconds}
        if step.reverse:
            data["direction"] = "CCW"
        if step.temperature_c is not None:
            data["temperature"] = {"value": str(step.temperature_c), "unit": "C"}
        return {"type": "STEP", "text": text,
                "annotations": [{"type": "TTS", "data": data, "position": position(text, phrase)}]}

    phrase = phrases.mode(step)
    text = _insert(step.text.strip(), SETTINGS, phrase)
    data = {}
    if step.time_seconds is not None:
        data["time"] = int(step.time_seconds) if step.time_seconds == int(step.time_seconds) else step.time_seconds
    if step.speed is not None:
        data["speed"] = step.speed
    if step.mode == "STEAMING":
        data["direction"] = "CCW" if step.reverse else "CW"
    if step.temperature_c is not None:
        data["temperature"] = {"value": str(step.temperature_c), "unit": "C"}
    if step.pulse_count:
        data["pulseCount"] = step.pulse_count
    if step.accessory:
        data["accessory"] = step.accessory
    if step.power:
        data["power"] = step.power
    return {"type": "STEP", "text": text,
            "annotations": [{"type": "MODE", "name": step.mode, "data": data, "position": position(text, phrase)}]}
