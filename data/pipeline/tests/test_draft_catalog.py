import json

import pytest
from jsonschema import Draft202012Validator

from draftory_data.draft_catalog import MEASUREMENTS_SHA, measurement_digest, publish
from draftory_data.simulation import identity
from draftory_data.source import DataError, canonical_bytes
from draftory_data.valuation import ROOT


def test_static_catalog_schema_digest_counts_and_reviewed_example_prices():
    path = ROOT / "data/publications/mlb-draft-2024-v1.json"
    catalog = json.loads(path.read_text("utf-8"))
    schema = json.loads((ROOT / "contracts/mlb-draft-catalog.schema.json").read_text("utf-8"))
    Draft202012Validator(schema).validate(catalog)
    assert path.read_bytes() == canonical_bytes(catalog) + b"\n"
    body = {k: v for k, v in catalog.items() if k != "id"}
    assert catalog["id"] == identity(body, "draft-catalog")
    assert catalog["researchMeasurementSha256"] == MEASUREMENTS_SHA
    players = catalog["players"]
    assert len(players) == len({p["id"] for p in players}) == 526
    assert len({p["profileId"] for p in players}) == 526
    expected = dict(
        zip(
            ("C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"),
            (77, 93, 100, 104, 77, 121, 92, 124, 526),
            strict=True,
        )
    )
    assert {pos: sum(pos in p["positions"] for p in players) for pos in expected} == expected
    summary = json.loads(
        (ROOT / "data/validation/valuation-eligibility-v1.json").read_text("utf-8")
    )
    for p in summary["examplesAndOutliers"]:
        entry = next(e for e in players if e["id"] == p["id"])
        assert entry["price"] == p["examplePrices"]["linear"]["DH"]
        assert entry["profileId"] == p["profileId"]


def test_measurement_pin_is_portable_but_rejects_changed_observations(tmp_path):
    research = dict.fromkeys(
        (
            "researchVersion",
            "datasetId",
            "sqlSha256",
            "fixtureSha256",
            "engineVersion",
            "transitionModelId",
            "repetitions",
            "batchSize",
        ),
        "test",
    )
    research["records"] = []
    original = measurement_digest(research)
    research["runnerSha256"] = "different-host-executable"
    assert measurement_digest(research) == original
    research["repetitions"] = "changed"
    assert measurement_digest(research) != original
    path = tmp_path / "research.json"
    path.write_text(json.dumps(research))
    with pytest.raises(DataError, match="reviewed M7A"):
        publish(tmp_path, path)
