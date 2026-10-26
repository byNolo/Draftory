"""Optional tests use the complete pinned official files, never an unofficial mirror."""

import pytest

from draftory_data.profiles import ProfileRequest, generate_profile


def profile(dataset, player, year, **kwargs):
    return generate_profile(
        dataset, ProfileRequest(player, "aggregate", ("AL", "NL"), year, year, **kwargs)
    )


def test_official_release_keys_and_identity_joins(official_dataset):
    data = official_dataset
    assert len(data.players) == 24270
    assert len(data.batting) == 128598
    assert len(data.appearances) == 128512
    assert len(data.teams) == 3614
    assert len(data.fielding) == 219479
    players = {p.player_id for p in data.players}
    teams = {(t.year, t.team_id, t.league_id) for t in data.teams}
    for row in [*data.batting, *data.appearances, *data.fielding]:
        assert row.player_id in players
        assert (row.year, row.team_id, row.league_id) in teams


def test_judge_2025_matches_verified_batting_record(official_dataset):
    result = profile(official_dataset, "judgeaa01", 2025)
    assert result["status"] == "ok"
    assert result["opportunities"] == 679
    assert result["includedTotals"]["AB"] == 541
    assert result["includedTotals"]["H"] == 179
    assert result["includedTotals"]["HR"] == 53
    assert result["probabilities"]["homeRun"] == pytest.approx(53 / 679)
    assert result["pooledDisplayStats"]["AVG"] == pytest.approx(179 / 541)


def test_soto_2022_trade_is_one_season_and_two_team_records(official_dataset):
    result = profile(official_dataset, "sotoju01", 2022)
    assert result["includedTotals"]["AB"] == 524
    assert result["includedTotals"]["H"] == 127
    assert result["includedTotals"]["HR"] == 27
    assert result["opportunities"] == 663
    assert len(result["seasonSamples"]) == 1
    assert result["seasonSamples"][0]["teamIds"] == ("SDN", "WAS")
    assert len(result["seasonSamples"][0]["sourceRows"]) == 2
    was = profile(official_dataset, "sotoju01", 2022, team_id="WAS")
    sdn = profile(official_dataset, "sotoju01", 2022, team_id="SDN")
    for field, value in result["includedTotals"].items():
        assert was["includedTotals"][field] + sdn["includedTotals"][field] == value


def test_observed_historical_inconsistencies_are_flagged(official_dataset):
    anomalies = {(s.player_id, s.year) for s in official_dataset.batting if s.quality_flags}
    assert anomalies == {("lahman:cantwto01", 1909), ("lahman:tayloci99", 1912)}
    assert profile(official_dataset, "cantwto01", 1909)["status"] == "insufficient_data"


def test_old_missing_pa_components_are_not_zero_filled(official_dataset):
    result = profile(official_dataset, "ruthba01", 1927)
    assert result["status"] == "insufficient_data"
    assert result["historicalTotals"]["HR"] == 60
    assert result["historicalTotals"]["SF"] is None
    assert result["probabilities"] is None
