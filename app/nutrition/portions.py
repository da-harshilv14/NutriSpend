import re
from dataclasses import dataclass

# Rough grams per common Indian serving unit. Deliberately a plain constant for
# now (YAGNI) — good enough to estimate, and every estimate is surfaced via HITL.
PORTION_GRAMS = {
    "bowl": 150,
    "katori": 150,
    "plate": 300,
    "glass": 250,
    "cup": 200,
    "piece": 50,
    "roti": 40,
    "chapati": 40,
    "slice": 30,
    "serving": 100,
    "tbsp": 15,
    "tablespoon": 15,
    "tsp": 5,
    "teaspoon": 5,
}
DIRECT_GRAM_UNITS = {"g", "gm", "gms", "gram", "grams"}
DEFAULT_GRAMS = 100.0

_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?)?\s*([a-zA-Z]+)?")


@dataclass(frozen=True)
class PortionEstimate:
    grams: float
    quantity: float
    unit: str
    is_estimated: bool  # True unless the user gave an exact weight in grams


def _singularize(unit: str) -> str:
    if unit.endswith("s") and unit[:-1] in PORTION_GRAMS:
        return unit[:-1]
    return unit


def resolve_portion(portion_text: str) -> PortionEstimate:
    text = (portion_text or "").strip().lower()
    match = _PATTERN.match(text)
    quantity_text, unit = (match.group(1), match.group(2)) if match else (None, None)
    quantity = float(quantity_text) if quantity_text else 1.0
    unit = unit or ""

    if unit in DIRECT_GRAM_UNITS:
        return PortionEstimate(grams=quantity, quantity=quantity, unit="g", is_estimated=False)

    singular = _singularize(unit)
    if singular in PORTION_GRAMS:
        grams = quantity * PORTION_GRAMS[singular]
        return PortionEstimate(grams=grams, quantity=quantity, unit=singular, is_estimated=True)

    # Unrecognized/absent unit -> assume one standard serving.
    return PortionEstimate(
        grams=quantity * DEFAULT_GRAMS, quantity=quantity, unit="serving", is_estimated=True
    )
