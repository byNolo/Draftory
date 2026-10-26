"""Shared scripted fixtures only; no historical-profile adapter or sampling model."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[3]
SCHEMAS = {
    name: json.loads((ROOT / "contracts" / f"simulation-{name}.schema.json").read_text("utf-8"))
    for name in ("input", "script", "result")
}
REGISTRY = Registry().with_resources(
    (schema["$id"], Resource.from_contents(schema)) for schema in SCHEMAS.values()
)


def fixture(name):
    return json.loads(
        (ROOT / "data/fixtures" / f"simulation-{name}.synthetic.json").read_text("utf-8")
    )


def validate(name, value):
    Draft202012Validator(SCHEMAS[name], registry=REGISTRY).validate(value)


def test_schemas_are_valid_and_prepared_input_is_complete():
    for schema in SCHEMAS.values():
        Draft202012Validator.check_schema(schema)
    value = fixture("input")
    validate("input", value)
    assert value["seed"] == "18446744073709551615"
    assert int(value["seed"]) == (1 << 64) - 1
    profiles = {p["id"] for p in value["profiles"]}
    batters = [b for team in value["teams"].values() for b in team["lineup"]]
    assert len({b["id"] for b in batters}) == 18
    assert all(b["profileId"] in profiles for b in batters)
    for profile in value["profiles"]:
        assert sum(profile["weights"].values()) == 1_000_000
        assert "synthetic-test-only" in profile["qualityFlags"]


def test_golden_game_reconciles_every_supported_counter():
    script = fixture("script")
    result = fixture("result")
    validate("script", script)
    validate("result", result)
    assert result["input"] == fixture("input")
    assert result["score"] == [1, 2]
    assert result["winner"] == "home"
    assert result["finalState"]["plateAppearances"] == len(script) == 56
    assert result["lineScore"][-1] == {"inning": 9, "away": 0, "home": 2}
    assert "eventLog" not in result
    for side, box in enumerate(result["teams"]):
        totals = box["totals"]
        for field, value in totals.items():
            assert sum(batter["stats"][field] for batter in box["batters"]) == value
        assert totals["hits"] == sum(
            totals[k] for k in ("singles", "doubles", "triples", "homeRuns")
        )
        assert (
            totals["plateAppearances"] == totals["atBats"] + totals["walks"] + totals["hitByPitch"]
        )
        assert totals["atBats"] == totals["hits"] + box["outsRecorded"]
        assert (
            totals["plateAppearances"] == box["outsRecorded"] + totals["runs"] + box["leftOnBase"]
        )
        assert totals["runs"] == totals["runsBattedIn"] == result["score"][side]
        key = ("away", "home")[side]
        assert sum(line[key] or 0 for line in result["lineScore"]) == totals["runs"]
        assert totals["intentionalWalks"] <= totals["walks"]


@pytest.mark.parametrize(
    "event",
    [
        {"kind": "otherAtBat"},
        {"kind": "sacrificeFly"},
        {"kind": "sacrificeHit"},
        {"kind": "walk"},
        {"kind": "walk", "intentional": None},
        {"kind": "single", "advanceSecond": True},
    ],
)
def test_unsupported_or_ambiguous_events_fail_the_shared_contract(event):
    with pytest.raises(ValidationError):
        validate("script", [event])


@pytest.mark.parametrize("replacement", [None, -1, 1.5, 1_000_001])
def test_missing_or_invalid_prepared_weight_is_not_imputed(replacement):
    value = fixture("input")
    value["profiles"][0]["weights"]["single"] = replacement
    with pytest.raises(ValidationError):
        validate("input", value)


def test_descriptive_other_at_bat_is_not_a_prepared_out_probability():
    value = fixture("input")
    weights = value["profiles"][0]["weights"]
    weights["otherAtBat"] = weights.pop("battedBallOut")
    with pytest.raises(ValidationError):
        validate("input", value)
    historical = json.loads(
        (ROOT / "data/fixtures/batting-profile.synthetic.json").read_text("utf-8")
    )
    with pytest.raises(ValidationError):
        validate("input", historical)


@pytest.mark.parametrize("change", ["missingBatter", "numericSeed", "unknownRules", "unknownField"])
def test_contract_rejects_invalid_game_shapes(change):
    value = fixture("input")
    if change == "missingBatter":
        value["teams"]["away"]["lineup"].pop()
    elif change == "numericSeed":
        value["seed"] = 123
    elif change == "unknownRules":
        value["rulesVersion"] = "unreviewed"
    else:
        value["extra"] = "ignored?"
    with pytest.raises(ValidationError):
        validate("input", value)


def test_summary_and_event_detail_shape_are_explicit():
    result = fixture("result")
    value = deepcopy(result)
    value["eventLog"] = []
    with pytest.raises(ValidationError):
        validate("result", value)
    value = deepcopy(result)
    value["input"]["detail"] = "events"
    with pytest.raises(ValidationError):
        validate("result", value)
