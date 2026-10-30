import json
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator
from test_defense import registry

from draftory_data.runner_transitions import MODEL, classify, upgrade
from draftory_data.source import DataError, canonical_bytes
from draftory_data.valuation import ROOT


def row(**changes):
    r = dict.fromkeys(
        "wp pb bk sb2 sb3 sbh cs2 cs3 csh oa pko1 pko2 pko3 sh sf tp othdp gdp "
        "roe fc othout outs_pre outs_post rbi_b rbi1 rbi2 rbi3 "
        "brout_b brout1 brout2 brout3".split(),
        "0",
    )
    r.update(
        dict.fromkeys(
            (
                "br1_pre br2_pre br3_pre br1_post br2_post br3_post run_b run1 run2 run3 "
                "lob_id1 lob_id2 lob_id3"
            ).split(),
            "",
        )
    )
    return {
        **r,
        "batter": "batter",
        "event": "S7.BX2(76)",
        "outs_post": "1",
        "brout_b": "7",
        **changes,
    }


def test_hit_tag_outs_retain_attempted_base_and_no_duplicate_hit():
    for base in (2, 3, 4):
        r = row(event=f"S7.BX{base if base < 4 else 'H'}(76)")
        t, label = classify(r, "single", 0, 0)
        assert label == "supported:hit-running-out"
        assert t[0] == (0, 5, 5, 5)
        assert json.loads(t[3])["outBases"][0] == base
    t, label = classify(
        row(event="D7.B-3", outs_post="0", br3_post="batter", brout_b="0"), "double", 0, 0
    )
    assert label == "supported:extra-batter-advance"
    assert t[0][0] == 3  # Event is still a double; ending base is separate.


def test_timing_requires_source_credited_run_and_inning_ending_tag():
    r = row(
        event="S7.3-H;1X3(75)",
        br1_pre="first",
        br3_pre="third",
        run3="third",
        rbi3="1",
        brout_b="0",
        brout1="7",
        outs_pre="2",
        outs_post="3",
        lob_id1="batter",
    )
    t, label = classify(r, "single", 2, 5)
    assert label == "supported:timing-third-out"
    assert json.loads(t[3])["runsBeforeOuts"]
    assert t[1][3]
    # Same geometry with a non-terminal out does not establish run/out chronology.
    r.update(outs_pre="0", outs_post="1", br1_post="batter", lob_id1="")
    assert classify(r, "single", 0, 5)[1] == "proxy:unresolved-run-out-order"
    passing = row(
        event="S7.1-H;2X3(75)",
        br1_pre="first",
        br2_pre="second",
        run1="first",
        rbi1="1",
        brout_b="0",
        brout2="7",
        outs_pre="2",
        outs_post="3",
        lob_id1="batter",
    )
    assert classify(passing, "single", 2, 3)[1] == "proxy:passing-at-timing-out"


def test_force_choice_is_proven_and_unsupported_cases_keep_mass():
    r = row(
        event="64(1)/FO/G6.B-1",
        br1_pre="first",
        lob_id1="batter",
        brout_b="0",
        outs_pre="2",
        outs_post="3",
        othout="1",
    )
    t, label = classify(r, "otherContact", 2, 1)
    assert label == "supported:force-choice"
    assert t[0] == (1, 0, 5, 5)
    assert t[2] == "fieldersChoice"
    assert json.loads(t[3])["outKinds"][1] == "force"
    for changes, expected in [
        ({"wp": "1"}, "proxy:compound-or-other-dp"),
        ({"event": "S7.BX2(7E6)"}, "proxy:error-or-appeal-out"),
        ({"event": "S7.BX2(76)#"}, "proxy:uncertain-source"),
        ({"brout_b": "0"}, "proxy:unproven-running-out"),
        ({"rbi_b": ""}, "proxy:unknown-rbi"),
    ]:
        transition, label = classify(row(**changes), "single", 0, 0)
        assert label == expected
        assert transition[3] is None
        assert transition[0] == (1, 5, 5, 5)  # Counted conservative fallback, not removed.


def test_new_fixture_schema_mass_and_legacy_profiles_unchanged():
    legacy = json.loads(
        (ROOT / "crates/baseball-sim/tests/fixtures/season-modern-2024.json").read_text("utf-8")
    )
    fixture = json.loads((ROOT / "data/fixtures/runner-season-2024-v1.json").read_text("utf-8"))
    schema = json.loads((ROOT / "contracts/runner-season-input.schema.json").read_text("utf-8"))
    Draft202012Validator(schema, registry=registry()).validate(fixture)
    assert fixture["profiles"] == legacy["profiles"]
    assert fixture["opponents"] == legacy["opponents"]
    model = fixture["config"]["contextualModel"]
    assert model["modelVersion"] == MODEL
    assert len(model["cells"]) == 72
    assert sum(c["observations"] for c in model["cells"]) == 211000
    assert all(sum(t["weight"] for t in c["choices"]) == 1000000 for c in model["cells"])
    bad = deepcopy(legacy)
    bad["config"]["defense"] = {}
    with pytest.raises(DataError, match="incompatible"):
        upgrade(bad, model)


def test_source_repreparation_is_identical(official_dataset, request, tmp_path):
    if not request.config.getoption("--retrosheet-source"):
        pytest.skip("Needs verified Retrosheet source")
    from draftory_data.runner_transitions import prepare

    model = prepare(tmp_path)
    fixture = json.loads((ROOT / "data/fixtures/runner-season-2024-v1.json").read_text("utf-8"))
    # In-memory tuples and decoded JSON arrays must produce exactly the same bytes.
    assert canonical_bytes(model) == canonical_bytes(fixture["config"]["contextualModel"])
