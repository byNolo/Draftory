import json
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator
from test_defense import registry

from draftory_data.opponents import prepare, select_players
from draftory_data.publication import validate_prepared
from draftory_data.simulation import identity
from draftory_data.source import DataError
from draftory_data.valuation import ROOT


def test_team_membership_ranking_stints_missing_and_ties():
    players = [{"id": f"lahman:p{i}"} for i in range(10)]
    rows = [
        (
            i,
            {
                "yearID": 2024,
                "teamID": "A",
                "playerID": f"p{i}",
                "stint": 1,
                "AB": 100,
                "BB": 0,
                "HBP": 0,
                "SH": 0,
                "SF": 0,
            },
        )
        for i in range(10)
    ]
    # A second stint for the same team sums once. Another team never contributes.
    rows += [
        (11, {**rows[9][1], "stint": 2, "AB": 1}),
        (12, {**rows[0][1], "teamID": "B", "AB": 999}),
    ]
    selected = select_players(players, rows, "A")
    assert selected[0] == (players[9], 101)
    assert selected[1][0] == players[0]
    assert len(selected) == 9
    with pytest.raises(DataError, match="Duplicate"):
        select_players(players, rows + [rows[0]], "A")
    with pytest.raises(DataError, match="Incomplete"):
        select_players(players, [(2, {**rows[0][1], "HBP": None})], "A")
    with pytest.raises(DataError, match="Fewer"):
        select_players(players[:8], rows, "A")


def test_published_opponents_identity_contract_and_profile_compatibility():
    p = json.loads((ROOT / "data/publications/opponents-2024-v1.json").read_text("utf-8"))
    assert p["id"] == identity({k: v for k, v in p.items() if k != "id"}, "opponents")
    schema = json.loads((ROOT / "contracts/opponents.schema.json").read_text("utf-8"))
    validator = Draft202012Validator(schema, registry=registry())
    validator.validate(p)
    assert len(p["opponents"]) == 9 and len(p["profiles"]) == 81
    profiles = {r["id"]: r for r in p["profiles"]}
    for r in profiles.values():
        validate_prepared(r)
        assert r["provenance"]["sourceId"] == p["sourceId"]
        assert r["provenance"]["policyId"] == p["policyId"]
        assert r["provenance"]["contextId"] == p["contextId"]
    for t in p["opponents"]:
        assert len({b["playerId"] for b in t["lineup"]}) == 9
        assert all(
            profiles[b["profileId"]]["provenance"]["playerId"] == b["playerId"] for b in t["lineup"]
        )
    bad = deepcopy(p)
    bad["year"] = 2023
    assert not validator.is_valid(bad)


def test_official_opponent_publication_reproduces_and_refuses_overwrite(request, tmp_path):
    source = request.config.getoption("--lahman-source")
    if not source:
        pytest.skip("Provide --lahman-source for official opponent reproduction")
    from pathlib import Path

    original = ROOT / "data/publications/opponents-2024-v1.json"
    output = tmp_path / "opponents.json"
    prepare(Path(source), ROOT / "data/processed/d1-2024", output)
    assert original.read_bytes() == output.read_bytes()
    output.write_text("changed", encoding="utf-8")
    with pytest.raises(DataError, match="immutable"):
        prepare(Path(source), ROOT / "data/processed/d1-2024", output)


def test_dashboard_golden_is_strict_versioned_and_has_no_inputs_or_logs():
    value = json.loads(
        (ROOT / "data/fixtures/dashboard-season-2024-v1.golden.json").read_text("utf-8")
    )
    schema = json.loads(
        (ROOT / "contracts/season-dashboard-summary.schema.json").read_text("utf-8")
    )
    validator = Draft202012Validator(schema, registry=registry())
    validator.validate(value)
    assert value["dashboard"]["opponentDefense"] == "neutral"
    assert len(value["dashboard"]["games"]) == 162
    assert len(value["dashboard"]["opponents"]) == 9
    assert sum(o["runsAllowed"] for o in value["dashboard"]["opponents"]) == value["runsAllowed"]
    assert "input" not in value
    invalid = deepcopy(value)
    invalid["dashboard"]["games"][0]["eventLog"] = []
    assert not validator.is_valid(invalid)
    invalid = deepcopy(value)
    invalid["dashboard"]["schemaVersion"] = "unknown"
    assert not validator.is_valid(invalid)
