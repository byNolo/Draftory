"""Keep acquisition provenance explicit before implementing source adapters."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = json.loads((ROOT / "contracts/source-manifest.schema.json").read_text(encoding="utf-8"))
FIXTURE = json.loads(
    (ROOT / "data/fixtures/source-manifest.synthetic.json").read_text(encoding="utf-8")
)
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def test_synthetic_manifest_matches_contract():
    Draft202012Validator.check_schema(SCHEMA)
    VALIDATOR.validate(FIXTURE)


@pytest.mark.parametrize("field", ["release", "url", "retrievedAt", "sha256", "files"])
def test_provenance_fields_are_required(field):
    manifest = deepcopy(FIXTURE)
    del manifest[field]
    with pytest.raises(ValidationError):
        VALIDATOR.validate(manifest)


@pytest.mark.parametrize(
    ("field", "value"),
    [("sha256", "not-a-checksum"), ("retrievedAt", "yesterday"), ("files", [])],
)
def test_invalid_provenance_is_rejected(field, value):
    manifest = deepcopy(FIXTURE)
    manifest[field] = value
    with pytest.raises(ValidationError):
        VALIDATOR.validate(manifest)
