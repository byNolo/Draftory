"""Validate public artifacts, CLI exit codes and byte-stable normalized output."""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from draftory_data.cli import main
from draftory_data.normalize import Appearance, Fielding, aggregate_seasons
from draftory_data.profiles import ProfileRequest, generate_profile
from draftory_data.source import canonical_bytes, digest

ROOT = Path(__file__).resolve().parents[3]


def validate(name, value):
    schema = json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(json.loads(canonical_bytes(value)))


@pytest.mark.parametrize("method", ["aggregate", "season_rate_mean", "season_rate_median"])
def test_profile_schema_and_failure_variant(dataset, method):
    for minimum in (1, 99):
        profile = generate_profile(
            dataset, ProfileRequest("synthetic01", method, ("AL",), min_seasons=minimum)
        )
        validate("batting-profile.schema.json", profile)
    invalid = json.loads(canonical_bytes(profile))
    invalid["probabilities"] = {}
    with pytest.raises(ValidationError):
        validate("batting-profile.schema.json", invalid)


def test_all_normalized_record_types_and_output_hashes(dataset, tmp_path):
    dataset.appearances = [Appearance("lahman:synthetic01", 2000, "A", "AL", {"C": 1}, {}, 2)]
    dataset.fielding = [
        Fielding("lahman:synthetic01", 2000, "A", "AL", 1, "C", {}, "Fielding.csv", 2)
    ]
    manifest = dataset.write(tmp_path / "first")
    validate("normalized-lahman-manifest.schema.json", manifest)
    for entry in manifest["files"]:
        path = tmp_path / "first" / entry["path"]
        assert digest(path) == entry["sha256"]
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert len(records) == entry["rows"]
        for record in records:
            validate("normalized-lahman-record.schema.json", record)
    assert dataset.write(tmp_path / "second") == manifest
    for path in (tmp_path / "first").iterdir():
        assert path.read_bytes() == (tmp_path / "second" / path.name).read_bytes()
    season = aggregate_seasons(dataset.batting)[0]
    assert asdict(season)["source_rows"] == (2,)


def test_cli_generates_inspectable_json_and_handles_errors(dataset, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("draftory_data.cli.Dataset.load", lambda _: dataset)
    target = tmp_path / "example.json"
    args = [
        "profile",
        "--source-dir",
        str(tmp_path),
        "--player",
        "synthetic01",
        "--leagues",
        "AL",
        "--output",
        str(target),
    ]
    assert main(args) == 0
    output = json.loads(capsys.readouterr().out)
    assert json.loads(target.read_text(encoding="utf-8")) == output
    assert main(args + ["--min-seasons", "99"]) == 3
    assert json.loads(capsys.readouterr().out)["status"] == "insufficient_data"
    assert main(args + ["--team", "unknown"]) == 2
    assert "Unknown team" in capsys.readouterr().err


def test_committed_synthetic_profile_fixture():
    path = ROOT / "data/fixtures/batting-profile.synthetic.json"
    fixture = json.loads(path.read_text(encoding="utf-8"))
    validate("batting-profile.schema.json", fixture)
    profile_id = fixture.pop("profileId")
    assert profile_id == "sha256:" + hashlib.sha256(canonical_bytes(fixture)).hexdigest()


def test_broken_relationships_are_not_published(dataset, tmp_path):
    from draftory_data.source import DataError

    dataset.players = []
    with pytest.raises(DataError, match="Unknown player reference"):
        dataset.write(tmp_path)
    assert not (tmp_path / "manifest.json").exists()
