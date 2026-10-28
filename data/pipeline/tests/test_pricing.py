import json
from copy import deepcopy
from fractions import Fraction as F

import pytest
from jsonschema import Draft202012Validator, ValidationError

from draftory_data import pricing_study
from draftory_data.draft_catalog import elite_body, publish, write_catalog
from draftory_data.pricing import (
    DEFAULT_BUDGET,
    POLICY_ID,
    price,
    prices,
    tier_boundaries,
    value_tier,
)
from draftory_data.simulation import identity
from draftory_data.source import DataError, canonical_bytes
from draftory_data.valuation import ROOT, sha, write


def test_pa_cache_is_bound_to_actual_inputs_runner_and_valid_usage(tmp_path, monkeypatch):
    monkeypatch.setattr(pricing_study, "research_input", lambda *_: {})
    runner = tmp_path / "runner"
    runner.write_bytes(b"synthetic runner identity")
    for seed in ("0", "1"):
        row = {"seed": seed, "pa": 680, "runsScored": 700}
        key = {
            "studyVersion": pricing_study.VERSION,
            "inputSha256": sha(canonical_bytes({"seed": seed})),
            "runnerSha256": sha(runner.read_bytes()),
            "seed": seed,
        }
        write(
            tmp_path / "native" / f"p-{seed}.json",
            {"key": key, "row": row, "rowSha256": sha(canonical_bytes(row))},
        )
    result = pricing_study.measure_pa([{"id": "p"}], {}, {}, runner, tmp_path, True)
    assert [r["pa"] for r in result["p"]] == [680, 680]
    path = tmp_path / "native/p-0.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    saved["row"]["pa"] = 0
    write(path, saved)
    with pytest.raises(DataError, match="cache"):
        pricing_study.measure_pa([{"id": "p"}], {}, {}, runner, tmp_path, True)
    saved["rowSha256"] = sha(canonical_bytes(saved["row"]))
    write(path, saved)
    with pytest.raises(DataError, match="Invalid measured"):
        pricing_study.measure_pa([{"id": "p"}], {}, {}, runner, tmp_path, True)


def test_curves_rounding_monotonicity_and_historical_pa_boundaries():
    assert price(F(0), F(0), F(100), 50, "linear", F(75)) == 1
    assert price(F(50), F(0), F(100), 50, "linear", F(75)) == 11
    assert price(F(50), F(0), F(100), 50, "elite", F(75)) == 8
    assert price(F(100), F(0), F(100), 700, "elite", F(75)) == 30
    for policy in ("linear", "elite", "confidence-discount", "tier-cap"):
        for pa in (50, 99, 100, 199, 200, 399, 400, 599, 600):
            quotes = [price(F(v), F(0), F(100), pa, policy, F(75)) for v in range(101)]
            assert quotes == sorted(quotes)
            assert all(1 <= q <= (20 if policy == "linear" else 30) for q in quotes)
    assert price(F(100), F(0), F(100), 50, "confidence-discount", F(75)) == 26
    assert price(F(100), F(0), F(100), 200, "confidence-discount", F(75)) == 30
    assert price(F(100), F(0), F(100), 199, "tier-cap", F(75)) == 17
    assert price(F(100), F(0), F(100), 200, "tier-cap", F(75)) == 30
    for pa in (49, 0, 100.5):
        with pytest.raises(DataError):
            price(F(50), F(0), F(100), pa, "elite", F(75))
    with pytest.raises(DataError):
        price(F(50), F(0), F(100), 100, "unknown", F(75))


def test_tiers_keep_equal_values_together_and_selected_policy_does_not_discount_pa_twice():
    values = {str(i): F(i // 5) for i in range(101)}
    boundaries = tier_boundaries(values)
    for v in set(values.values()):
        assert len({value_tier(values[k], boundaries) for k in values if values[k] == v}) == 1
    players = [{"id": pid, "pa": 50 if int(pid) % 2 else 700} for pid in values]
    quotes = prices(values, players, "elite")
    assert [quotes[p["id"]] for p in players] == sorted(quotes.values())
    for p in players:
        p["pa"] = 700
    assert prices(values, players, "elite") == quotes


def test_pure_publication_is_deterministic_preserves_facts_and_protects_existing_files(tmp_path):
    original = {
        "schemaVersion": "1.0.0",
        "players": [
            {"id": "a", "pa": 50, "profileId": "prepared:a", "price": 1},
            {"id": "b", "pa": 700, "profileId": "prepared:b", "price": 20},
        ],
    }
    before = deepcopy(original)
    result = elite_body(original, {"a": F(0), "b": F(100)})
    assert original == before
    assert result == elite_body(deepcopy(original), {"b": F(100), "a": F(0)})
    assert result["defaultBudget"] == DEFAULT_BUDGET == 65
    assert result["pricingPolicy"] == POLICY_ID
    assert [p["price"] for p in result["players"]] == [1, 30]
    assert [p["profileId"] for p in result["players"]] == [
        p["profileId"] for p in before["players"]
    ]
    out = tmp_path / "catalog-v2.json"
    catalog = {"id": identity(result, "draft-catalog"), **result}
    write_catalog(out, catalog)
    write_catalog(out, catalog)
    assert out.read_bytes() == canonical_bytes(catalog) + b"\n"
    with pytest.raises(DataError, match="Immutable"):
        write_catalog(out, {**catalog, "defaultBudget": 70})
    with pytest.raises(DataError, match="identities"):
        elite_body(original, {"a": F(0)})


def test_committed_v2_catalog_schema_digest_and_immutable_profile_membership():
    old = json.loads(
        (ROOT / "data/publications/mlb-draft-2024-v1.json").read_text(encoding="utf-8")
    )
    path = ROOT / "data/publications/mlb-draft-2024-v2.json"
    new = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(
        (ROOT / "contracts/mlb-draft-catalog-v2.schema.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)
    validator.validate(new)
    assert path.read_bytes() == canonical_bytes(new) + b"\n"
    assert new["id"] != old["id"]
    assert new["id"] == identity({k: v for k, v in new.items() if k != "id"}, "draft-catalog")
    for field in (
        "datasetId",
        "sourceId",
        "sourceSqlSha256",
        "profilePolicyId",
        "contextId",
        "researchMeasurementSha256",
    ):
        assert old[field] == new[field]
    assert len(new["players"]) == len({p["id"] for p in new["players"]}) == 526
    for a, b in zip(old["players"], new["players"], strict=True):
        assert {k: v for k, v in a.items() if k != "price"} == {
            k: v for k, v in b.items() if k not in ("price", "valueTier")
        }
    with pytest.raises(ValidationError):
        validator.validate({**new, "defaultBudget": 90})


def test_verified_producer_reproduces_both_catalog_versions_when_local_research_is_available():
    research = ROOT / "data/processed/m7a/research.json"
    publication = ROOT / "data/processed/d1-2024"
    if not research.exists() or not (publication / "manifest.json").exists():
        pytest.skip("Requires verified local M7A research and 2024 publication")
    for version, policy in (("v1", "m7a-linear-1-20-v1"), ("v2", POLICY_ID)):
        actual = publish(publication, research, policy)
        assert (
            canonical_bytes(actual) + b"\n"
            == (ROOT / f"data/publications/mlb-draft-2024-{version}.json").read_bytes()
        )
    pa_path = ROOT / "data/processed/m8c2/pa-pricing.json"
    drafts_path = ROOT / "data/processed/m8c2/draft-budgets.json"
    if pa_path.exists() and drafts_path.exists():
        pa = json.loads(pa_path.read_text(encoding="utf-8"))
        drafts = json.loads(drafts_path.read_text(encoding="utf-8"))
        actual = pricing_study.compact_summary(
            pa, drafts, publish(publication, research, POLICY_ID)
        )
        expected = json.loads(
            (ROOT / "data/validation/pricing-pa-v1.json").read_text(encoding="utf-8")
        )
        assert actual == expected
        with pytest.raises(DataError, match="Summary inputs"):
            pricing_study.compact_summary(
                pa, {**drafts, "paStudySha256": "0" * 64}, publish(publication, research, POLICY_ID)
            )


def test_committed_experiment_covers_all_budgets_policies_and_complete_round_counts():
    report = json.loads((ROOT / "data/validation/pricing-pa-v1.json").read_text(encoding="utf-8"))
    assert sum(b["count"] for b in report["paBands"]) == 526
    assert report["nativePaSeasons"] == 1052
    assert report["nativePaGames"] == 170424
    for histogram in report["priceHistograms"].values():
        assert sum(histogram.values()) == 526
    cases = [
        dict(zip(report["draftExperiments"]["columns"], row, strict=True))
        for row in report["draftExperiments"]["rows"]
    ]
    assert {c["budget"] for c in cases} == {65, 70, 75, 90}
    assert len(cases) == 64
    assert sum(c["trials"] for c in cases) == report["totalDrafts"] == 6400
    for case in cases:
        assert (
            sum(
                case[k]
                for k in ("selectedLow", "selectedMiddle", "selectedAboveAverage", "selectedElite")
            )
            == 9 * case["trials"]
        )
    choices = report["choicesByRound"]
    assert len(choices) == 64
    for case in choices:
        assert len(case["countsOneTwoThree"]) == 9
        assert all(sum(round_counts) == 100 for round_counts in case["countsOneTwoThree"])
    assert (
        sum(
            sum((i + 1) * n for i, n in enumerate(round_counts))
            for c in choices
            for round_counts in c["countsOneTwoThree"]
        )
        == report["checkedSafeOffers"]
    )


def test_historical_engine_snapshot_is_pinned_and_tampering_fails(tmp_path, monkeypatch):
    source = pricing_study.pricing_engine_source()
    assert pricing_study.sha(source) == pricing_study.PRICING_ENGINE_SHA
    historical = json.loads((ROOT / "data/validation/pricing-pa-v1.json").read_text("utf-8"))
    assert historical["draftEngineSourceSha256"] == pricing_study.PRICING_ENGINE_SHA
    target = tmp_path / "data/research/pricing-draft-engine-v1.ts"
    target.parent.mkdir(parents=True)
    target.write_bytes(source + b"// changed")
    monkeypatch.setattr(pricing_study, "ROOT", tmp_path)
    with pytest.raises(DataError, match="Historical pricing engine integrity"):
        pricing_study.pricing_engine_source()
