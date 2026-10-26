"""Exercise real SQLite migrations and immutable exports, without cloud services."""

import json
import sqlite3
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from draftory_data.normalize import Appearance, Player, TeamSeason
from draftory_data.publication import (
    build_publication,
    export_publication,
    validate_prepared,
)
from draftory_data.simulation import PreparationPolicy
from draftory_data.source import DataError, canonical_bytes

ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = ROOT / "infra/d1/migrations"
POLICY = PreparationPolicy("ordinary-out-proxy-v1", min_pa=1)


def publication_fixture(dataset):
    value = deepcopy(dataset)
    value.players.append(Player("lahman:synthetic02", "synthetic02", "Second Batter", {}, 3))
    value.teams.append(TeamSeason(2000, "B", "NL", "F", {"name": "Second Team"}, 9))
    original = value.batting[0]
    value.batting = [
        original,
        replace(
            original,
            team_id="B",
            league_id="NL",
            stint=2,
            source_row=9,
            counts=deepcopy(original.counts),
        ),
        replace(
            original,
            player_id="lahman:synthetic02",
            source_row=10,
            counts=deepcopy(original.counts),
        ),
    ]
    value.appearances = [
        Appearance("lahman:synthetic01", 2000, "A", "AL", {"C": 20, "DH": None}, {}, 2),
        Appearance("lahman:synthetic01", 2000, "B", "NL", {"C": 10, "DH": 2}, {}, 3),
        Appearance("lahman:synthetic02", 2000, "A", "AL", {"1B": 10, "DH": 3}, {}, 4),
    ]
    return value


def database():
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys=ON")
    for path in sorted(MIGRATIONS.glob("[0-9]*.sql")):
        db.executescript(path.read_text("utf-8"))
    return db


def test_deterministic_export_repeatable_import_and_shared_fixture(dataset, tmp_path):
    data = publication_fixture(dataset)
    sql, manifest = build_publication(data, 2000, POLICY)
    # The fixture is also consumed by the real local Worker integration suite.
    assert sql.encode() == (ROOT / "data/fixtures/d1-player-data.synthetic.sql").read_bytes()
    assert build_publication(data, 2000, POLICY) == (sql, manifest)
    exported = export_publication(data, 2000, POLICY, tmp_path, MIGRATIONS)
    assert exported["sqlitePageBytes"] > 0
    assert (tmp_path / "import.sql").read_bytes() == sql.encode()
    with database() as db:
        db.executescript(sql)
        changes = db.total_changes
        db.executescript(sql)
        assert db.total_changes == changes
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("SELECT count(*) FROM mlb_profiles").fetchone()[0] == 2
        stints = db.execute(
            "SELECT counts_json FROM mlb_batting_stints WHERE player_id='lahman:synthetic01'"
        ).fetchall()
        assert sum(json.loads(row[0])["AB"] for row in stints) == 200
        # Three appearance records do not multiply the two traded batting stints.
        assert manifest["rowCounts"]["mlb_batting_stints"] == 3
        assert (
            db.execute("SELECT games FROM mlb_dataset_positions WHERE position='C'").fetchone()[0]
            == 30
        )
        # Incomplete traded DH observations are not treated as a known total.
        assert (
            db.execute("SELECT count(*) FROM mlb_dataset_positions WHERE position='DH'").fetchone()[
                0
            ]
            == 1
        )
        assert db.execute(
            "SELECT games FROM mlb_position_appearances WHERE games IS NULL"
        ).fetchone() == (None,)
        schema = json.loads((ROOT / "contracts/simulation-input.schema.json").read_text())
        validator = Draft202012Validator({"$ref": "#/$defs/profile", "$defs": schema["$defs"]})
        for (payload,) in db.execute("SELECT payload_json FROM mlb_profiles"):
            profile = json.loads(payload)
            validator.validate(profile)
            validate_prepared(profile)
            assert profile["weights"]["battedBallOut"] == 0
            assert profile["weights"]["otherContact"] > 0
        assert sorted(manifest["metadata"]["positionCounts"].values()) == [1, 1, 1]


def test_export_rejects_tampering_and_foreign_keys(dataset):
    sql, _ = build_publication(publication_fixture(dataset), 2000, POLICY)
    with database() as db:
        db.executescript(sql)
        before = db.execute("SELECT display_name FROM mlb_players ORDER BY id").fetchall()
        with pytest.raises(sqlite3.IntegrityError):
            db.executescript(sql.replace("Synthetic Batter", "Changed Batter"))
        assert db.execute("SELECT display_name FROM mlb_players ORDER BY id").fetchall() == before
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO mlb_player_seasons VALUES ('unknown','unknown',2000)")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE mlb_dataset_profiles SET player_id='unknown'")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE mlb_position_appearances SET games=-1")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE mlb_profiles SET payload_json='{}'")


def test_incomplete_import_has_no_publication_and_cannot_finalize(dataset):
    sql, manifest = build_publication(publication_fixture(dataset), 2000, POLICY)
    sql = sql[: sql.rfind("INSERT INTO mlb_publications")]
    with database() as db:
        db.executescript(sql)
        assert db.execute("SELECT count(*) FROM mlb_publications").fetchone()[0] == 0
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO mlb_publications VALUES (?,99,'{}')", (manifest["datasetId"],))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO mlb_publications VALUES (?,2,'{}')", (manifest["datasetId"],))


def test_small_missing_empty_and_policy_versions(dataset):
    data = publication_fixture(dataset)
    data.batting[0].counts["SF"] = None
    sql, manifest = build_publication(data, 2000, POLICY)
    assert manifest["metadata"]["profileCount"] == 1
    assert len(manifest["excludedPlayers"]) == 1
    with database() as db:
        db.executescript(sql)
        assert db.execute("SELECT id FROM mlb_players").fetchall() == [("lahman:synthetic02",)]
    with pytest.raises(DataError, match="No profiles qualify"):
        build_publication(data, 2000, replace(POLICY, min_pa=10000))
    with pytest.raises(DataError):
        build_publication(data, 1999, POLICY)
    _, other = build_publication(data, 2000, replace(POLICY, prior_pa=100))
    assert other["datasetId"] != manifest["datasetId"]
    assert other["metadata"]["context"]["policyId"] != manifest["metadata"]["context"]["policyId"]


def test_corrupt_prepared_weights_fail(dataset):
    sql, _ = build_publication(publication_fixture(dataset), 2000, POLICY)
    with database() as db:
        db.executescript(sql)
        profile = json.loads(
            db.execute("SELECT payload_json FROM mlb_profiles LIMIT 1").fetchone()[0]
        )
    for change in ({"homeRun": -1}, {"homeRun": True}, {"battedBallOut": 1}):
        invalid = deepcopy(profile)
        invalid["weights"].update(change)
        with pytest.raises(DataError):
            validate_prepared(invalid)


def test_shared_api_contract_uses_exact_prepared_fixture(dataset):
    schemas = [
        json.loads((ROOT / "contracts" / name).read_text("utf-8"))
        for name in ("player-data-api.schema.json", "simulation-input.schema.json")
    ]
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas
    )
    api = next(s for s in schemas if s["$id"].endswith("player-data-api.schema.json"))
    fixture = json.loads((ROOT / "data/fixtures/player-data-api.synthetic.json").read_text())
    Draft202012Validator(api, registry=registry).evolve(
        schema={"$ref": api["$id"] + "#/$defs/batchResponse"}
    ).validate(fixture)
    sql, summary = build_publication(publication_fixture(dataset), 2000, POLICY)
    assert fixture["datasetId"] == summary["datasetId"]
    with database() as db:
        db.executescript(sql)
        assert fixture["profiles"] == [
            json.loads(row[0])
            for row in db.execute("SELECT payload_json FROM mlb_profiles ORDER BY player_id")
        ]


def test_export_cli(dataset, tmp_path, capsys, monkeypatch):
    from draftory_data.cli import main

    monkeypatch.setattr("draftory_data.cli.Dataset.load", lambda _: publication_fixture(dataset))
    args = [
        "export-d1",
        "--source-dir",
        str(tmp_path),
        "--year",
        "2000",
        "--contact-policy",
        "ordinary-out-proxy-v1",
        "--min-pa",
        "1",
        "--output-dir",
        str(tmp_path / "export"),
        "--migrations-dir",
        str(MIGRATIONS),
    ]
    assert main(args) == 0
    result = json.loads(capsys.readouterr().out)
    manifest = json.loads((tmp_path / "export/manifest.json").read_text())
    assert result["datasetId"] == manifest["datasetId"]
    assert result["rowCounts"] == manifest["rowCounts"]
    assert result["sqlSha256"] == manifest["sqlSha256"]
    assert result["excludedPlayerCount"] == len(manifest["excludedPlayers"])
    assert len(canonical_bytes(result)) < 4000


def test_verified_release_export_and_trade(official_dataset, tmp_path):
    summary = export_publication(
        official_dataset, 2024, PreparationPolicy("ordinary-out-proxy-v1"), tmp_path, MIGRATIONS
    )
    assert summary["metadata"]["profileCount"] > 500
    with database() as db:
        db.executescript((tmp_path / "import.sql").read_text())
        rows = db.execute(
            "SELECT counts_json FROM mlb_batting_stints WHERE player_id='lahman:arraelu01'"
        ).fetchall()
        assert len(rows) == 2
        assert sum(json.loads(row[0])["H"] for row in rows) == 200
        assert (
            db.execute(
                "SELECT count(*) FROM mlb_dataset_profiles WHERE player_id='lahman:arraelu01'"
            ).fetchone()[0]
            == 1
        )
        judge = json.loads(
            db.execute(
                "SELECT payload_json FROM mlb_profiles WHERE player_id='lahman:judgeaa01'"
            ).fetchone()[0]
        )
        existing = json.loads(
            (ROOT / "crates/baseball-sim/tests/fixtures/season-modern-2024.json").read_text()
        )
        golden = next(
            p for p in existing["profiles"] if p["provenance"]["playerId"] == "lahman:judgeaa01"
        )
        assert judge["weights"] == golden["weights"]
