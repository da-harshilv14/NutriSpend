from app.db.models import NutritionReference
from app.nutrition.lookup import LookupResult, NutritionCandidate, needs_confirmation
from app.nutrition.portions import resolve_portion
from app.nutrition.scaling import scale_nutrition


def _ref(source="dataset", cal=100, protein=None, carbs=None):
    return NutritionReference(
        name="X", name_normalized="x", source=source,
        calories_per_100g=cal, protein_per_100g=protein, carbs_per_100g=carbs,
    )


def _result(*candidates):
    return LookupResult(query="q", candidates=list(candidates))


def _cand(source="dataset", score=1.0, match="exact"):
    return NutritionCandidate(reference=_ref(source=source), score=score, match_type=match)


# --- portions ---
def test_portion_bowls_are_estimated():
    e = resolve_portion("2 bowls")
    assert e.grams == 300 and e.is_estimated


def test_portion_grams_are_exact():
    e = resolve_portion("200g")
    assert e.grams == 200 and e.is_estimated is False


def test_portion_unknown_defaults_to_serving():
    e = resolve_portion("banana")
    assert e.grams == 100 and e.is_estimated


# --- scaling ---
def test_scaling_scales_and_keeps_none():
    snap = scale_nutrition(_ref(cal=200, protein=10, carbs=None), 50)
    assert snap["calories"] == 100 and snap["protein"] == 5 and snap["carbs"] is None


# --- needs_confirmation policy ---
def test_exact_dataset_auto_logs():
    assert needs_confirmation(_result(_cand("dataset", 1.0, "exact"))) is False


def test_websearch_always_confirms():
    assert needs_confirmation(_result(_cand("websearch", 1.0, "websearch"))) is True


def test_low_fuzzy_confirms():
    assert needs_confirmation(_result(_cand("dataset", 0.5, "fuzzy"))) is True


def test_high_fuzzy_auto_logs():
    assert needs_confirmation(_result(_cand("dataset", 0.9, "fuzzy"))) is False


def test_near_tie_confirms():
    result = _result(_cand("dataset", 0.9, "fuzzy"), _cand("dataset", 0.85, "fuzzy"))
    assert needs_confirmation(result) is True


def test_nothing_found_confirms():
    assert needs_confirmation(_result()) is True
