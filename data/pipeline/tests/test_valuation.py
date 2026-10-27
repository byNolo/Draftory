"""Synthetic policy/assignment tests plus a small existing-native-runner integration."""

import itertools
import json
import random
import sys
from copy import deepcopy
from dataclasses import replace

import pytest

from draftory_data.draft_research import (
    INF,
    POSITIONS,
    CompletionCosts,
    EligibilityPolicy,
    assignment,
    eligibility,
    experiment,
    percentile_ranks,
    price_quotes,
)
from draftory_data.normalize import Appearance, TeamSeason
from draftory_data.publication import export_publication
from draftory_data.simulation import PreparationPolicy
from draftory_data.source import DataError
from draftory_data.valuation import (
    ROOT,
    estimate,
    load_fixture,
    load_publication,
    native_rows,
    rank_correlation,
    research_input,
    value_players,
)


def test_positions_thresholds_nulls_dh_and_generic_of_are_explicit():
    player = {"pa": 80, "appearances": {"C": 10, "SS": 9, "OF": 40, "CF": None, "DH": 0}}
    assert eligibility(player, EligibilityPolicy("strict", 10)) == ("C",)
    assert eligibility(player, EligibilityPolicy("dh", 10, True)) == ("C", "DH")
    assert eligibility(player, EligibilityPolicy("broad", 10, True, True)) == (
        "C",
        "LF",
        "CF",
        "RF",
        "DH",
    )
    assert eligibility(player, EligibilityPolicy("pa", 10, True, min_pa=100)) == ()
    with pytest.raises(DataError):
        EligibilityPolicy("invalid", 0)


def test_migrated_publication_preserves_trades_missing_positions_and_profiles(dataset, tmp_path):
    original = replace(dataset.batting[0], year=2024)
    traded = replace(original, team_id="B", league_id="NL", stint=2, source_row=3)
    value = replace(
        dataset,
        batting=[original, traded],
        teams=[TeamSeason(2024, "A", "AL", "F", {}, 2), TeamSeason(2024, "B", "NL", "F", {}, 3)],
        appearances=[
            Appearance("lahman:synthetic01", 2024, "A", "AL", {"C": 10, "DH": 0}, {}, 2),
            Appearance("lahman:synthetic01", 2024, "B", "NL", {"C": None, "DH": 0}, {}, 3),
        ],
    )
    before = deepcopy(value)
    export_publication(
        value,
        2024,
        PreparationPolicy("ordinary-out-proxy-v1", min_pa=1),
        tmp_path,
        ROOT / "infra/d1/migrations",
    )
    records, manifest = load_publication(tmp_path, ROOT / "infra/d1/migrations")
    assert value == before
    assert len(records) == 1
    row = records[0]
    assert row["pa"] == 200 and row["stintCount"] == 2
    assert row["appearances"]["C"] is None
    assert row["appearances"]["DH"] == 0
    assert row["appearances"]["CF"] is None
    assert row["profile"]["sampleOpportunities"] == 200
    assert manifest["metadata"]["context"]["id"] == row["profile"]["provenance"]["contextId"]
    with (tmp_path / "import.sql").open("a") as stream:
        stream.write("-- changed\n")
    with pytest.raises(DataError, match="integrity"):
        load_publication(tmp_path, ROOT / "infra/d1/migrations")


def test_changed_model_fixture_is_rejected_before_native(tmp_path):
    path = tmp_path / "fixture.json"
    path.write_text("{}")
    with pytest.raises(DataError, match="pinned"):
        load_fixture(path, {})


def test_hungarian_matches_exhaustive_assignments_including_missing_edges():
    rng = random.Random(31)
    for _ in range(30):
        costs = [[rng.choice([INF, 1, 2, 3, 7, 11]) for _ in range(4)] for _ in range(3)]
        expected = min(
            sum(costs[i][j] for i, j in enumerate(p)) for p in itertools.permutations(range(4), 3)
        )
        result = assignment(costs)
        if expected >= INF:
            assert result is None
        else:
            assert result[0] == expected
            assert len(set(result[1])) == 3
    assert assignment([]) == (0, [])
    assert assignment([[1], [1]]) is None


def test_completion_enforces_shared_identity_instead_of_independent_slot_minima():
    pools = {"C": ["flex"], "DH": ["flex", "dh"]}
    solver = CompletionCosts(pools, {("flex", "C"): 1, ("flex", "DH"): 1, ("dh", "DH"): 3})
    assert solver.minimum(("C", "DH")) == (4, {"C": "flex", "DH": "dh"})
    assert solver.minimum(("C",), frozenset({"flex"})) is None
    assert (
        CompletionCosts({"C": ["x"], "DH": ["x"]}, {("x", "C"): 1, ("x", "DH"): 1}).minimum(
            ("C", "DH")
        )
        is None
    )


def test_cheapest_candidate_bound_keeps_exact_cost_after_exclusions():
    ids = [f"p{i:02d}" for i in range(30)]
    pools = dict.fromkeys(POSITIONS, ids)
    quotes = {(pid, pos): i + 1 for pos in POSITIONS for i, pid in enumerate(ids)}
    solver = CompletionCosts(pools, quotes)
    assert solver.minimum(POSITIONS)[0] == sum(range(1, 10))
    assert solver.minimum(POSITIONS, frozenset(ids[:9]))[0] == sum(range(10, 19))
    assert solver.minimum(POSITIONS, frozenset(ids[20:]))[0] == sum(range(1, 10))


def test_prices_monotone_elite_premium_and_slot_scarcity_are_currency_only():
    values = {"low": -20, "mid": 0, "high": 20}
    pools = {"DH": list(values), "C": ["mid", "high"]}
    original = deepcopy(values)
    linear = price_quotes(values, pools, "linear")
    elite = price_quotes(values, pools, "elite")
    scarce = price_quotes(values, pools, "scarcity")
    assert linear["low", "DH"] == elite["low", "DH"] == 1
    assert linear["high", "DH"] == 20 and elite["high", "DH"] == 30
    assert linear["low", "DH"] < linear["mid", "DH"] < linear["high", "DH"]
    assert scarce["mid", "C"] > scarce["mid", "DH"]
    assert values == original
    # Linear in measured value, not in percentile rank.
    unequal = {"a": 0, "b": 1, "c": 100}
    assert price_quotes(unequal, {"DH": list(unequal)}, "linear")["b", "DH"] == 1
    assert percentile_ranks({"a": 3, "b": 3, "c": 5}) == {"a": 0.25, "b": 0.25, "c": 1}
    assert rank_correlation({"a": 1, "b": 2}, {"a": 2, "b": 1}) == pytest.approx(-1)
    assert rank_correlation({"a": 1}, {"a": 1}) is None
    with pytest.raises(DataError):
        price_quotes({"bad": float("nan")}, {}, "linear")


def draft_fixture():
    ids = [f"p{i}" for i in range(9)]
    pools = {pos: [pid] for pos, pid in zip(POSITIONS, ids, strict=True)}
    pools["DH"] = ["p0", "p8"]  # The only catcher is also the most attractive DH.
    quotes = {(pid, pos): 1 for pos, pool in pools.items() for pid in pool}
    quotes["p8", "DH"] = 2
    values = dict.fromkeys(ids, 0)
    values["p0"] = 10
    return pools, quotes, values


def test_greedy_dead_end_differs_from_reserve_and_protected_offer_design():
    pools, quotes, values = draft_fixture()
    kwargs = {"budget": 10, "trials": 40, "seed": 17, "order": ("DH", *POSITIONS[:-1])}
    greedy = experiment(values, pools, quotes, offers="position", selection="greedy", **kwargs)
    reserve = experiment(values, pools, quotes, offers="position", selection="reserve", **kwargs)
    protected = experiment(values, pools, quotes, offers="global", selection="protected", **kwargs)
    assert greedy["failures"] == {"choiceDestroyedCompletion": 40}
    assert greedy["completionWilson95"][1] > 0
    assert reserve["completionRate"] == protected["completionRate"] == 1
    assert 0 < reserve["completionWilson95"][0] < 1
    assert reserve["simulatedTrials"] == reserve["trials"] == 40
    assert protected["protectedInsertions"] > 0
    assert protected == experiment(
        values, pools, quotes, offers="global", selection="protected", **kwargs
    )
    impossible = experiment(
        values, pools, quotes, offers="position", selection="reserve", **{**kwargs, "budget": 9}
    )
    assert not impossible["initiallyFeasible"]
    assert impossible["simulatedTrials"] == 0
    assert impossible["completionWilson95"] is None


def test_sampling_uncertainty_is_repeat_variability_not_real_world_confidence():
    sample = estimate([-2, 0, 2])
    assert sample["mean"] == 0
    assert sample["monteCarloSe"] == pytest.approx(2 / (3**0.5))
    with pytest.raises(DataError):
        estimate([1])


def test_existing_native_runner_preserves_profiles_pairs_seeds_and_checks_cache(tmp_path):
    runner = (
        ROOT
        / "target/release/examples"
        / ("calibrate.exe" if sys.platform == "win32" else "calibrate")
    )
    if not runner.exists():
        pytest.skip("Build the existing release calibrate example for native research integration")
    fixture = json.loads(
        (ROOT / "crates/baseball-sim/tests/fixtures/season-modern-2024.json").read_text()
    )
    profile = fixture["profiles"][0]
    player = {"id": profile["provenance"]["playerId"], "profile": profile}
    before = deepcopy(fixture)
    rows = value_players([player], fixture, player, runner, tmp_path, 2, False)
    assert fixture == before
    assert rows[0]["marginalReplicateTeamRuns"] == [0, 0]
    assert rows[0]["marginalTeamRunsPer162"]["mean"] == 0
    assert research_input(fixture, player, player, "homogeneous")["userLineupKind"] == "synthetic"
    cache = tmp_path / "native/000-reference.json"
    inputs = [research_input(fixture, player, player, "reference")]
    assert len(native_rows(inputs, runner, 2, cache, True)) == 2
    cached = json.loads(cache.read_text())
    cached["rows"][0]["runsScored"] += 1
    cache.write_text(json.dumps(cached))
    with pytest.raises(DataError, match="checksum"):
        native_rows(inputs, runner, 2, cache, True)
