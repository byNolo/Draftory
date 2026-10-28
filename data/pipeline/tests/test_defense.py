"""Error-avoidance contracts and preparation: separate from batting/prices."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from draftory_data.defense import SCALE, effect, prepare, verify_dev, write_supplement
from draftory_data.defense_research import FieldingLine
from draftory_data.simulation import identity
from draftory_data.source import DataError, canonical_bytes
from draftory_data.valuation import ROOT


def line(**counts):
    return FieldingLine(
        "test",
        2024,
        "SS",
        {"PO": 100, "A": 100, "E": 0, "InnOuts": 300, **counts},
        ("A",),
        (("Fielding.csv", 2),),
    )


def registry():
    schemas = [json.loads(p.read_text("utf-8")) for p in (ROOT / "contracts").glob("*.json")]
    return Registry().with_resources(
        (s["$id"], Resource.from_contents(s)) for s in schemas if "$id" in s
    )


def test_reliability_boundaries_missing_and_zero():
    reference = {"errors": 20, "chances": 1000}
    assert effect(None, reference) == ("unknown", SCALE)
    assert effect(line(E=None), reference) == ("unknown", SCALE)
    assert effect(line(InnOuts=299), reference) == ("insufficient", SCALE)
    status, ratio = effect(line(), reference)
    assert status == "observed" and ratio == 833333
    assert effect(line(PO=0, A=0, E=0), reference) == ("insufficient", SCALE)
    assert effect(line(), {"errors": 0, "chances": 1000}) == ("unknown", SCALE)
    assert effect(line(E=20), reference)[1] > SCALE


def test_supplement_content_ids_profile_identity_and_schema():
    s = json.loads((ROOT / "data/publications/defense-2024-v1.json").read_text("utf-8"))
    body = {k: v for k, v in s.items() if k != "id"}
    assert identity(body, "defense-supplement") == s["id"]
    schema = json.loads((ROOT / "contracts/defense-supplement.schema.json").read_text("utf-8"))
    Draft202012Validator(schema, registry=registry()).validate(s)
    assert len(s["profiles"]) == 788
    assert len({(p["playerId"], p["year"], p["position"]) for p in s["profiles"]}) == 788
    assert s["model"]["supportedPositions"] == ["1B", "2B", "3B", "SS"]
    for p in s["profiles"]:
        assert identity({k: v for k, v in p.items() if k != "id"}, "defense") == p["id"]
        if p["status"] != "observed":
            assert p["errorRatio"] == SCALE
    bad = deepcopy(s)
    bad["profiles"][0]["year"] = 2023
    assert not Draft202012Validator(schema, registry=registry()).is_valid(bad)


def test_opt_in_input_contract_and_legacy_contract_are_distinct():
    x = json.loads((ROOT / "data/fixtures/defense-season-2024-v1.json").read_text("utf-8"))
    schema = json.loads((ROOT / "contracts/defense-season-input.schema.json").read_text("utf-8"))
    Draft202012Validator(schema, registry=registry()).validate(x)
    old = json.loads((ROOT / "contracts/season-input.schema.json").read_text("utf-8"))
    assert not Draft202012Validator(old, registry=registry()).is_valid(x)
    bad = deepcopy(x)
    bad["config"]["defense"]["assignments"][0]["position"] = "DH"
    assert not Draft202012Validator(schema, registry=registry()).is_valid(bad)


def test_development_integrity_rejects_missing_and_tampered_files(tmp_path):
    with pytest.raises(DataError, match="integrity"):
        verify_dev(tmp_path)
    (tmp_path / "2024plays.zip").write_bytes(b"not official bytes")
    with pytest.raises(DataError, match="integrity"):
        verify_dev(tmp_path)


def test_immutable_supplement_does_not_overwrite_existing_bytes(tmp_path):
    path = tmp_path / "supplement.json"
    write_supplement(path, {"synthetic": 1})
    write_supplement(path, {"synthetic": 1})
    with pytest.raises(DataError, match="immutable"):
        write_supplement(path, {"synthetic": 2})


def test_source_backed_supplement_reproduces(request, tmp_path):
    source = request.config.getoption("--lahman-source")
    retro = request.config.getoption("--retrosheet-source")
    dev = ROOT / "data/raw/retrosheet-defense-2024"
    publication = ROOT / "data/processed/d1-2024"
    if (
        not source
        or not retro
        or not (dev / "2024plays.zip").exists()
        or not (publication / "import.sql").exists()
    ):
        pytest.skip("Supply both source options and acquire verified 2024 development plays/pilot")
    output = tmp_path / "supplement.json"
    s, r = prepare(Path(source), Path(retro), dev, publication, output, tmp_path / "report.json")
    official = json.loads((ROOT / "data/publications/defense-2024-v1.json").read_text("utf-8"))
    assert canonical_bytes(s) == canonical_bytes(official)
    assert sum(t["modifiableROE"] for t in r["training"]) == 1754
    assert r["development"]["modifiableROE"] == 880
    selected = next(
        t for t in r["reliability"] if t["minInnings"] == 100 and t["priorChances"] == 1000
    )
    assert all(x["logLossChangePerChance"] < 0 for x in selected["scores"])
