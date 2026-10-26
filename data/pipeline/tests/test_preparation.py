"""Research model boundaries, source verification and cross-language prepared input."""

import json
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest
from conftest import stint
from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from draftory_data.cli import main
from draftory_data.profiles import ProfileRequest, generate_profile
from draftory_data.simulation import (
    ENGINE_OUTCOMES,
    PreparationPolicy,
    fractions,
    identity,
    integer_weights,
    league_context,
    map_outcomes,
    prepare_game,
    prepare_profile,
)
from draftory_data.source import DataError, canonical_bytes

ROOT = Path(__file__).resolve().parents[3]
POLICY = PreparationPolicy("ordinary-out-proxy-v1", min_pa=1)
SCHEMAS = {
    name: json.loads((ROOT / "contracts" / f"{name}.schema.json").read_text("utf-8"))
    for name in (
        "simulation-input",
        "simulation-result",
        "simulation-preparation",
        "batting-profile",
    )
}
REGISTRY = Registry().with_resources(
    (s["$id"], Resource.from_contents(s)) for s in SCHEMAS.values()
)


def profile(dataset, method="aggregate", **kwargs):
    # JSON boundary converts tuple-valued producer fields to arrays.
    return json.loads(
        canonical_bytes(
            generate_profile(dataset, ProfileRequest("synthetic01", method, ("AL",), **kwargs))
        )
    )


def validate(name, value):
    Draft202012Validator(SCHEMAS[name], registry=REGISTRY).validate(value)


def test_explicit_lossy_mapping_conserves_and_reports_mass(dataset):
    dataset.batting = [stint(AB=100, H=30, SO=20, BB=10, IBB=3, SH=2, SF=3)]
    historical = profile(dataset)
    before = deepcopy(historical)
    mapped, audit = map_outcomes(historical["probabilities"], POLICY)
    assert sum(mapped.values()) == 1
    assert mapped["walk"] == pytest.approx(10 / 110)  # IBB not added again.
    assert mapped["battedBallOut"] == pytest.approx(50 / 110)
    assert audit["excludedSacrificeMass"] == pytest.approx(5 / 115)
    assert audit["retainedMass"] + audit["excludedSacrificeMass"] == pytest.approx(1)
    assert historical == before
    with pytest.raises(DataError, match="explicitly select"):
        map_outcomes(historical["probabilities"], PreparationPolicy())


def test_default_policy_and_equal_season_confidence_are_conservative(dataset):
    policy = PreparationPolicy("ordinary-out-proxy-v1")
    context = league_context(dataset, policy, 2000, 2002)
    pooled = prepare_profile(profile(dataset), dataset, policy, context)
    assert pooled["effectiveSamplePa"] == 140
    assert pooled["playerBlendWeight"] == pytest.approx(140 / 340)
    for method in ("season_rate_mean", "season_rate_median"):
        with pytest.raises(DataError, match="below minimum"):
            prepare_profile(profile(dataset, method), dataset, policy, context)


@pytest.mark.parametrize("method", ["aggregate", "season_rate_mean", "season_rate_median"])
@pytest.mark.parametrize(
    "filters", [{}, {"team_id": "A"}, {"franchise_id": "F"}, {"start_year": 2000, "end_year": 2000}]
)
def test_all_profile_methods_and_filters_remain_distinct_and_valid(dataset, method, filters):
    historical = profile(dataset, method, **filters)
    context = league_context(dataset, POLICY, 2000, 2002)
    audit = prepare_profile(historical, dataset, POLICY, context)
    prepared = audit["preparedProfile"]
    assert prepared["provenance"]["sourceProfileId"] == historical["profileId"]
    assert prepared["provenance"]["playerId"] == historical["playerId"]
    assert sum(prepared["weights"].values()) == 1_000_000
    assert audit["maxRoundingError"] < 1e-6


def test_smoothing_is_explicit_and_zero_prior_preserves_mapped_rates(dataset):
    historical = profile(dataset, start_year=2000, end_year=2000)
    context = league_context(dataset, POLICY, 2000, 2002)
    audit = prepare_profile(historical, dataset, POLICY, context)
    for key in ENGINE_OUTCOMES:
        expected = (
            audit["playerBlendWeight"] * audit["mappedProbabilities"][key]
            + (1 - audit["playerBlendWeight"]) * context["mappedProbabilities"][key]
        )
        assert audit["smoothedProbabilities"][key] == pytest.approx(expected)
    policy = replace(POLICY, prior_pa=0)
    context = league_context(dataset, policy, 2000, 2002)
    audit = prepare_profile(historical, dataset, policy, context)
    assert audit["playerBlendWeight"] == 1
    assert audit["smoothedProbabilities"] == audit["mappedProbabilities"]


@pytest.mark.parametrize("field", ["SF", "HBP", "SO"])
def test_missing_or_excluded_seasons_are_not_imputed(dataset, field):
    dataset.batting[1] = stint(2001, row=3, AB=10, **{field: None})
    context = league_context(dataset, POLICY, 2000, 2002)
    assert context["excludedPlayerSeasons"]
    with pytest.raises(DataError, match="excludes seasons"):
        prepare_profile(profile(dataset), dataset, POLICY, context)


def test_inconsistent_stint_excludes_whole_traded_season(dataset):
    dataset.batting = [stint(AB=100, H=20), stint(stint_id=2, row=3, AB=1, H=2)]
    with pytest.raises(DataError, match="no complete"):
        league_context(dataset, POLICY, 2000, 2000)


@pytest.mark.parametrize("mutation", ["missing", "negative", "nan", "version", "tamperedFacts"])
def test_forged_or_malformed_profiles_rejected_with_useful_errors(dataset, mutation):
    historical = profile(dataset)
    context = league_context(dataset, POLICY, 2000, 2002)
    if mutation == "missing":
        del historical["probabilities"]["walk"]
    elif mutation in ("negative", "nan"):
        historical["probabilities"]["walk"] = -1 if mutation == "negative" else float("nan")
    elif mutation == "version":
        historical["schemaVersion"] = "999"
    else:
        historical["includedTotals"]["H"] += 1
    with pytest.raises(DataError):
        prepare_profile(historical, dataset, POLICY, context)


@pytest.mark.parametrize("rates", [{}, {"single": 1}, {"single": -1}])
def test_invalid_vectors_fail(rates):
    with pytest.raises(DataError):
        fractions(rates)


def test_largest_remainders_are_deterministic_and_never_add_mass_to_true_zero():
    rates = dict.fromkeys(ENGINE_OUTCOMES, Fraction(0))
    for key in ENGINE_OUTCOMES[:3]:
        rates[key] = Fraction(1, 3)
    assert integer_weights(rates) == dict(
        zip(ENGINE_OUTCOMES, [333334, 333333, 333333, 0, 0, 0, 0, 0], strict=True)
    )


def test_tiny_sample_old_year_and_mismatched_context_fail(dataset):
    policy = PreparationPolicy("ordinary-out-proxy-v1")
    context = league_context(dataset, policy, 2000, 2002)
    with pytest.raises(DataError, match="below minimum"):
        prepare_profile(profile(dataset, start_year=2002), dataset, policy, context)
    historical = profile(dataset)
    with pytest.raises(DataError, match="policy window"):
        prepare_profile(historical, dataset, replace(policy, min_year=2001), context)
    context["historicalProbabilities"]["single"] += 0.1
    with pytest.raises(DataError, match="digest"):
        prepare_profile(historical, dataset, policy, context)


def test_prepared_game_and_companion_audit_use_shared_schemas(dataset):
    historical = profile(dataset)
    context = league_context(dataset, POLICY, 2000, 2002)
    game, audit = prepare_game(dataset, [historical] * 9, [historical] * 9, POLICY, context, "42")
    for schema in SCHEMAS.values():
        Draft202012Validator.check_schema(schema)
    # JSON serialization is part of the contract boundary, not Python tuples.
    audit = json.loads(canonical_bytes(audit))
    validate("simulation-input", game)
    validate("simulation-preparation", audit)
    assert audit["inputId"] == identity(game, "game")
    assert len(game["profiles"]) == 1
    assert len({b["id"] for t in game["teams"].values() for b in t["lineup"]}) == 18
    del game["sampling"]
    with pytest.raises(ValidationError):
        validate("simulation-input", game)


def test_oversized_seed_is_a_validation_error_before_integer_conversion(dataset):
    with pytest.raises(DataError, match="canonical decimal u64"):
        prepare_game(dataset, [{}] * 9, [{}] * 9, POLICY, {}, "1" * 5000)


def test_cli_writes_linked_artifacts_and_rejects_malformed_profiles(
    dataset, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr("draftory_data.cli.Dataset.load", lambda _: dataset)
    path = tmp_path / "historical.json"
    path.write_bytes(canonical_bytes(profile(dataset)))
    target = tmp_path / "game.json"
    args = [
        "prepare-game",
        "--source-dir",
        "unused",
        "--away-profiles",
        *([str(path)] * 9),
        "--home-profiles",
        *([str(path)] * 9),
        "--contact-policy",
        "ordinary-out-proxy-v1",
        "--min-pa",
        "1",
        "--context-start-year",
        "2000",
        "--context-end-year",
        "2002",
        "--seed",
        "42",
        "--output",
        str(target),
    ]
    assert main(args) == 0
    game = json.loads(target.read_text())
    audit = json.loads(target.with_suffix(".preparation.json").read_text())
    validate("simulation-input", game)
    validate("simulation-preparation", audit)
    assert audit["inputId"] == identity(game, "game")
    path.write_text("[]")
    assert main(args) == 2
    assert "Invalid historical profile" in capsys.readouterr().err


def test_official_fixture_is_reproducible_from_pinned_source(official_dataset):
    dataset = official_dataset
    policy = PreparationPolicy("ordinary-out-proxy-v1")
    context = league_context(dataset, policy, 2025, 2025)
    judge, soto = [
        json.loads(
            canonical_bytes(
                generate_profile(
                    dataset, ProfileRequest(player, "aggregate", ("AL", "NL"), 2025, 2025)
                )
            )
        )
        for player in ("judgeaa01", "sotoju01")
    ]
    assert judge["opportunities"] == 679
    assert soto["opportunities"] == 714
    game, audit = prepare_game(
        dataset,
        [judge, soto, judge, soto, judge, soto, judge, soto, judge],
        [soto, judge, soto, judge, soto, judge, soto, judge, soto],
        policy,
        context,
        "2025",
        "events",
    )
    expected = json.loads(
        (ROOT / "crates/baseball-sim/tests/fixtures/lahman-modern-game.json").read_text("utf-8")
    )
    assert game == expected
    validate("simulation-input", game)
    validate("simulation-preparation", json.loads(canonical_bytes(audit)))
