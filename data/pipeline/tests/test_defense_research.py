"""Defense research boundaries, null semantics and official-source reconciliation."""

import json
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest

from draftory_data.defense_research import (
    COUNTS,
    ROOT,
    FieldingLine,
    aggregate_fielding,
    contact_event,
    distribution,
    error_experiment,
    field_coverage,
    native_diagnostic,
    play_flags,
    ratio,
    study,
    total,
)
from draftory_data.source import DataError, canonical_bytes, digest


def row(pos="SS", team="A", stint=1, **counts):
    return {
        "playerID": "test01",
        "yearID": 2024,
        "teamID": team,
        "lgID": "AL",
        "stint": stint,
        "POS": pos,
        **dict.fromkeys(COUNTS, 0),
        **counts,
    }


def aggregate(main, split=()):
    return aggregate_fielding(
        {"Fielding.csv": list(enumerate(main, 2)), "FieldingOFsplit.csv": list(enumerate(split, 2))}
    )


def test_trade_and_positions_do_not_multiply_or_cross_join():
    lines = aggregate(
        [row(PO=10, A=20, E=0), row(team="B", stint=2, PO=5, A=7, E=1), row(pos="2B", PO=100)]
    )
    ss = next(r for r in lines if r.position == "SS")
    assert ss.counts["PO"] == 15 and ss.chances == 43
    assert ss.teams == ("A", "B") and len(ss.rows) == 2
    assert next(r for r in lines if r.position == "2B").counts["PO"] == 100


def test_generic_of_not_added_to_specific_splits():
    lines = aggregate([row(pos="OF", PO=90)], [row(pos="LF", PO=30), row(pos="CF", PO=60)])
    assert {r.position: r.counts["PO"] for r in lines} == {"LF": 30, "CF": 60}


def test_duplicate_and_conflicting_source_rows_rejected():
    with pytest.raises(DataError, match="Duplicate"):
        aggregate([row(), row()])
    with pytest.raises(DataError, match="Conflicting"):
        aggregate([row(pos="LF", PO=3)], [row(pos="LF", PO=4)])
    assert len(aggregate([row(pos="LF", PO=3)], [row(pos="LF", PO=3)])) == 1
    with pytest.raises(DataError, match="Invalid fielding count"):
        aggregate([row(E=-1)])


def test_unknown_stint_propagates_without_changing_other_counts():
    line = aggregate([row(E=0, PO=4), row(stint=2, team="B", E=None, PO=3)])[0]
    assert line.counts["E"] is None and line.chances is None
    assert line.counts["PO"] == 7
    assert total([]) is None and total([0, 0]) == 0 and total([None, 0]) is None
    assert ratio(0, 10) == 0 and ratio(0, 0) is None and ratio(None, 10) is None


def test_error_experiment_respects_sample_denominator_and_position_baseline():
    line = aggregate([row(PO=100, A=0, E=0, InnOuts=900)])[0]
    metric = error_experiment(line, Fraction(1, 50))
    assert metric["shrunkErrorRate"] == 0.01
    assert metric["avoidedErrorsPer1000Chances"] == 10
    assert error_experiment(line, Fraction(1, 100))["shrunkErrorRate"] == 0.005
    assert error_experiment(line, Fraction(1, 50), min_innings=301) is None
    assert error_experiment(aggregate([row(InnOuts=900)])[0], Fraction(1, 50)) is None
    missing = FieldingLine(
        line.player, line.year, line.position, {**line.counts, "E": None}, line.teams, line.rows
    )
    assert error_experiment(missing, Fraction(1, 50)) is None
    with pytest.raises(DataError):
        error_experiment(line, Fraction(1, 50), prior=-1)


def test_coverage_does_not_convert_missing_to_zero_or_continuity():
    c = field_coverage([(2, row(yearID=1900, E=None)), (3, row(yearID=2024, E=0))])
    assert c["E"] == {
        "known": 1,
        "missing": 1,
        "zero": 1,
        "firstKnownYear": 2024,
        "lastKnownYear": 2024,
    }
    assert distribution([None, 1, 3, 5, 7])["median"] == 4


def test_ground_opportunity_flag_is_not_assumed_equivalent_to_state():
    r = {"outs_pre": "1", "br1_pre": "runner", "br2_pre": "", "br3_pre": "", "dpopp": "0"}
    assert play_flags(r) == (1, 1, True)
    assert play_flags({**r, "outs_pre": "2"}) == (2, 1, False)
    with pytest.raises(DataError):
        play_flags({**r, "outs_pre": "3"})


def test_residual_contact_includes_reaches_but_not_strikeouts_or_hits():
    r = dict.fromkeys(("single", "double", "triple", "hr", "k"), "0")
    r["ab"] = "1"
    assert contact_event(r) == "otherContact"
    assert contact_event({**r, "k": "1"}) is None
    assert contact_event({**r, "single": "1"}) == "single"
    assert contact_event({**r, "double": "1"}) == "double"


def test_small_native_diagnostic_preserves_input_and_repeats(tmp_path):
    runner = ROOT / "target/release/examples/season.exe"
    if not runner.exists():
        runner = ROOT / "target/release/examples/season"
    if not runner.exists():
        pytest.skip("Build the native release season example for event diagnostics")
    fixture = ROOT / "crates/baseball-sim/tests/fixtures/season-modern-2024.json"
    before = digest(fixture)
    a = native_diagnostic(runner, tmp_path)
    b = native_diagnostic(runner, tmp_path)
    assert a == b and digest(fixture) == before
    assert a["counts"]["gdp"] == 275
    assert a["counts"]["eligibleOtherContact"] == 1152
    assert a["innings1to8Counts"]["pa"] < a["counts"]["pa"]


def test_official_research_reproducibility_and_joins(request, tmp_path):
    source = request.config.getoption("--lahman-source")
    retro = request.config.getoption("--retrosheet-source")
    publication = ROOT / "data/processed/d1-2024"
    if not source or not retro or not (publication / "import.sql").exists():
        pytest.skip("Supply both official source paths and generate the 2024 pilot publication")
    a = study(Path(source), Path(retro), publication, tmp_path, None)
    b = study(Path(source), Path(retro), publication, tmp_path, None)
    assert canonical_bytes(a) == canonical_bytes(b)
    assert a["pool"]["positions"]["SS"]["eligiblePlayers"] == 77
    assert all(p["eligibleMissingRecord"] == 0 for p in a["pool"]["positions"].values())
    assert a["retrosheet"]["counts"]["gdp"] == 6250
    assert a["retrosheet"]["classificationCounts"]["ground-double-play"] == 6250
    assert abs(a["retrosheet"]["expectedGDPOnObservedStates"] - 6250) < 0.01
    ar = [r for r in a["pool"]["playerPositionRecords"] if r["playerId"] == "lahman:arraelu01"]
    assert next(r for r in ar if r["position"] == "1B")["counts"]["PO"] == 441
    checked = json.loads((ROOT / "data/validation/defense-research-v1.json").read_text("utf-8"))
    trimmed = deepcopy(a)
    trimmed.pop("researchId")
    for key in ("pool", "tables", "retrosheet", "teamChecks2024"):
        # The committed compact result intentionally excludes the complete per-player audit.
        expected = deepcopy(trimmed[key])
        if key == "pool":
            expected.pop("playerPositionRecords")
        if key == "tables":
            for table in expected.values():
                table.pop("eras")
        assert canonical_bytes(checked[key]) == canonical_bytes(expected)
