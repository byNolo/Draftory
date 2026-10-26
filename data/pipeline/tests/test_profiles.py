"""Aggregation, accounting, missingness, tiny samples and reproducibility."""

import math
from dataclasses import replace

import pytest
from conftest import stint

from draftory_data.normalize import aggregate_seasons, sum_counts
from draftory_data.profiles import (
    ProfileRequest,
    display_stats,
    generate_profile,
    normalize_vector,
    outcome_counts,
    pa_count,
)
from draftory_data.source import DataError


def request(method="aggregate", **kwargs):
    return ProfileRequest("synthetic01", method, ("AL",), **kwargs)


def test_weighted_aggregate_differs_from_equal_season_mean_and_median(dataset):
    pooled = generate_profile(dataset, request())
    avg = generate_profile(dataset, request("season_rate_mean"))
    med = generate_profile(dataset, request("season_rate_median"))
    assert pooled["opportunities"] == 140
    assert pooled["rawOutcomeRates"]["homeRun"] == pytest.approx(10 / 140)
    assert avg["rawOutcomeRates"]["homeRun"] == pytest.approx((0.1 + 0 + 0) / 3)
    assert med["rawOutcomeRates"]["homeRun"] == 0
    assert med["normalizationFactor"] != pytest.approx(1)
    for profile in (pooled, avg, med):
        assert profile["status"] == "ok"
        assert math.fsum(profile["probabilities"].values()) == pytest.approx(1)
        assert all(0 <= p <= 1 for p in profile["probabilities"].values())


def test_traded_player_aggregates_once_and_team_filter_applies_first(dataset):
    dataset.batting = [stint(AB=10, H=4), stint(team="B", stint_id=2, row=3, AB=20, H=2)]
    full = generate_profile(dataset, request(start_year=2000, end_year=2000))
    assert full["includedTotals"]["AB"] == 30
    assert full["includedTotals"]["H"] == 6
    assert len(full["seasonSamples"]) == 1
    team = generate_profile(dataset, request(team_id="A"))
    assert team["includedTotals"]["AB"] == 10
    assert team["pooledDisplayStats"]["AVG"] == 0.4


def test_duplicate_stint_is_rejected():
    row = stint(AB=10)
    with pytest.raises(DataError, match="Duplicate"):
        aggregate_seasons([row, row])


@pytest.mark.parametrize("field", ["HBP", "SF", "SH", "SO", "H", "AB", "HR"])
def test_missing_inputs_exclude_whole_season_without_imputing(dataset, field):
    dataset.batting = [stint(**({"AB": 10, "H": 3} | {field: None}))]
    result = generate_profile(dataset, request())
    assert result["status"] == "insufficient_data"
    assert result["historicalTotals"][field] is None
    assert result["probabilities"] is None
    assert result["excludedSeasons"]


def test_missing_one_stint_propagates_instead_of_using_partial_season(dataset):
    dataset.batting = [stint(AB=10, H=3), stint(stint_id=2, row=3, AB=5, HBP=None)]
    result = generate_profile(dataset, request())
    assert result["historicalTotals"]["AB"] == 15
    assert result["historicalTotals"]["HBP"] is None
    assert result["opportunities"] == 0


@pytest.mark.parametrize(
    "counts",
    [
        {"AB": -1},
        {"AB": 2, "H": 3},
        {"AB": 10, "H": 1, "HR": 2},
        {"AB": 10, "H": 5, "SO": 6},
        {"AB": 10, "BB": 1, "IBB": 2},
    ],
)
def test_inconsistent_facts_are_retained_but_not_profiled(dataset, counts):
    dataset.batting = [stint(**counts)]
    result = generate_profile(dataset, request())
    assert result["historicalTotals"] == dataset.batting[0].counts
    assert result["status"] == "insufficient_data"


def test_pa_components_and_intentional_walks_not_double_counted():
    counts = stint(AB=10, H=4, BB=3, IBB=2, HBP=1, SH=1, SF=2, SO=2).counts
    assert pa_count(counts) == 17
    assert sum(outcome_counts(counts).values()) == 17
    assert outcome_counts(counts)["otherAtBat"] == 4
    assert display_stats(counts)["OBP"] == 8 / 16


def test_rates_from_counts_not_rounded_display_values():
    counts = stint(AB=7, H=3, BB=2, HBP=1, SF=1, **{"2B": 1, "HR": 1}).counts
    result = display_stats(counts)
    assert result["AVG"] == 3 / 7
    assert result["SLG"] == 7 / 7
    assert result["OBP"] == 6 / 11
    assert result["OPS"] == 6 / 11 + 1


def test_zero_opportunities_and_pure_walk_sample(dataset):
    dataset.batting = [stint()]
    assert generate_profile(dataset, request())["status"] == "insufficient_data"
    dataset.batting = [stint(BB=1)]
    result = generate_profile(dataset, request())
    assert result["probabilities"]["walk"] == 1
    assert result["pooledDisplayStats"]["AVG"] is None
    assert "no-small-sample-smoothing" in result["qualityFlags"]
    assert generate_profile(dataset, request(min_season_pa=2))["status"] == "insufficient_data"


def test_min_seasons_and_empty_scope(dataset):
    result = generate_profile(dataset, request(min_seasons=4))
    assert result["status"] == "insufficient_data"
    assert result["probabilities"] is None
    assert generate_profile(dataset, request(start_year=2099))["status"] == "insufficient_data"


@pytest.mark.parametrize("method", ["aggregate", "season_rate_mean", "season_rate_median"])
def test_team_and_franchise_scope_for_each_method(dataset, method):
    result = generate_profile(dataset, request(method, team_id="A"))
    assert [s["year"] for s in result["seasonSamples"]] == [2000, 2001]
    franchise = generate_profile(dataset, request(method, franchise_id="F"))
    assert franchise["includedTotals"]["AB"] == 130


def test_year_bounds_and_profile_hash_reproducibility(dataset):
    result = generate_profile(dataset, request(start_year=2000, end_year=2001))
    assert [s["year"] for s in result["seasonSamples"]] == [2000, 2001]
    dataset.batting.reverse()
    assert generate_profile(dataset, request(start_year=2000, end_year=2001)) == result
    assert generate_profile(dataset, request())["profileId"] != result["profileId"]
    dataset.provenance = {**dataset.provenance, "release": "different-release"}
    assert (
        generate_profile(dataset, request(start_year=2000, end_year=2001))["profileId"]
        != result["profileId"]
    )


def test_min_threshold_changes_id(dataset):
    assert (
        generate_profile(dataset, request())["profileId"]
        != generate_profile(dataset, request(min_season_pa=2))["profileId"]
    )


@pytest.mark.parametrize("rates", [{"x": 0}, {"x": -1}, {"x": math.nan}, {"x": math.inf}])
def test_invalid_probability_mass_rejected(rates):
    with pytest.raises(DataError):
        normalize_vector(rates)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start_year": 2001, "end_year": 2000},
        {"min_season_pa": 0},
        {"min_seasons": 0},
        {"team_id": "A", "franchise_id": "F"},
    ],
)
def test_invalid_request_rejected(kwargs):
    with pytest.raises(DataError):
        request(**kwargs)


def test_explicit_leagues_and_unknown_ids(dataset):
    with pytest.raises(DataError):
        ProfileRequest("synthetic01", "aggregate", ())
    for req in (
        replace(request(), player_id="unknown"),
        replace(request(), leagues=("unknown",)),
        replace(request(), team_id="unknown"),
        replace(request(), franchise_id="unknown"),
    ):
        with pytest.raises(DataError):
            generate_profile(dataset, req)


def test_counts_keep_nulls():
    rows = [stint(AB=10).counts, stint(AB=20, BB=None).counts]
    assert sum_counts(rows)["AB"] == 30
    assert sum_counts(rows)["BB"] is None


def test_disjoint_season_medians_do_not_invent_a_fallback(dataset):
    dataset.batting = [
        stint(2000, AB=1, H=1, HR=1),
        stint(2001, row=3, BB=1),
        stint(2002, row=4, AB=1, SO=1),
    ]
    result = generate_profile(dataset, request("season_rate_median"))
    assert result["status"] == "insufficient_data"
    assert result["probabilities"] is None
    assert "component-medians-have-zero-mass" in result["qualityFlags"]
