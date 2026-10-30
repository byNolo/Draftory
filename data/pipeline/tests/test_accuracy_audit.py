"""Audit failures must not silently excuse changed inputs or miscount opportunities."""

import json

import pytest

from draftory_data import accuracy_audit as audit
from draftory_data.source import DataError


def test_hit_difference_reconciles_volume_and_rate_without_claiming_causality():
    d = audit.decomposition(40, 8, 42, 10)
    assert d["volume"] == pytest.approx(0.4)
    assert d["rate"] == pytest.approx(1.6)
    assert d["volume"] + d["rate"] == pytest.approx(d["total"])


def test_native_trace_extensions_preserve_legacy_summary_probe(tmp_path):
    runner = audit.ROOT / "target/release/examples/audit_accuracy.exe"
    if not runner.exists():
        pytest.skip("Build native audit example for summary/events probe")
    value = json.loads(
        (audit.ROOT / "crates/baseball-sim/tests/fixtures/season-modern-2024.json").read_text(
            "utf-8"
        )
    )
    value["games"] = 2
    path = tmp_path / "inputs.json"
    path.write_text(json.dumps([value]), "utf-8")
    traced = json.loads(audit.run_native(runner, path, 1, 1, 20261029))
    summary = json.loads(audit.run_native(runner, path, 1, 0, 20261029))
    assert "runnerMetrics" in traced
    assert audit.without_trace_observations(traced) == audit.without_trace_observations(summary)


def test_gdp_uses_residual_contacts_and_actual_eligible_states():
    cells = [[0] * 24 for _ in range(3)]
    cells[0][0], cells[0][1], cells[0][17] = 10, 5, 5
    cells[1][0], cells[1][1], cells[1][17] = 4, 3, 2
    cells[2][1] = 1
    d = audit.gdp_factors(cells)
    # Runner on first with two outs (index 17) is not GDP-eligible.
    assert d["eligible"] == 3
    assert d["stateEligiblePerPA"] == 0.25
    assert d["contactPerPA"] * d["eligiblePerContact"] * d["gdpPerEligible"] == pytest.approx(
        1 / 20
    )


def test_preparation_comparison_only_accepts_reversible_diagnostic_names():
    assert audit.preparation_differences({"displayName": "Peña"}, {"displayName": "PeÃ±a"})
    with pytest.raises(DataError, match="Unexpected"):
        audit.preparation_differences({"weight": 2}, {"weight": 1})
    with pytest.raises(DataError, match="Unexpected"):
        audit.preparation_differences({"displayName": "Peña"}, {"displayName": "Other"})


def test_source_selection_keeps_omitted_events_out_of_fit_denominator(monkeypatch, tmp_path):
    (tmp_path / "prepared").mkdir()
    cells = [
        {
            "event": "otherContact",
            "outs": o,
            "baseMask": b,
            "choices": [{"weight": 200000, "destinations": [0, 0, 5, 5]}],
        }
        for o in range(3)
        for b in range(8)
    ]
    (tmp_path / "prepared/transitions.json").write_text(json.dumps({"cells": cells}), "utf-8")
    monkeypatch.setattr(audit, "WORK", tmp_path)

    def row(**overrides):
        keys = (
            "sh sf sb2 sb3 sbh cs2 cs3 csh pko1 pko2 pko3 wp pb bk othdp tp k_safe "
            "pa ab single double triple hr k roe dpopp gdp ground bip othout fc oa "
            "outs_pre outs_post"
        ).split()
        r = dict.fromkeys(keys, "0")
        r.update(
            dict.fromkeys(
                "br1_pre br2_pre br3_pre br1_post br2_post br3_post run_b run1 run2 run3".split(),
                "",
            )
        )
        r.update(dict.fromkeys("brout1 brout2 brout3 rbi1 rbi2 rbi3".split(), "0"))
        r.update(
            gametype="regular",
            pbp="full",
            inning="1",
            gid="game",
            top_bot="0",
            pa="1",
            ab="1",
            batter="b",
            hittype="G",
        )
        return {**r, **overrides}

    rows = [
        row(single="1", outs_post="1", br1_pre="r", br1_post="b", brout1="8"),
        row(pa="0", ab="0", outs_pre="1", outs_post="2", cs2="1"),
        row(ab="0", sf="1", outs_post="1"),
        row(gdp="1", ground="1", othout="1", br1_pre="r", outs_post="2"),
    ]
    monkeypatch.setattr(audit.retrosheet, "zip_rows", lambda *args, **kwargs: iter(rows))
    d = audit.source_plays(2024, tmp_path)
    assert d["counts"]["paIncludingSacrifices"] == 3
    assert d["factors"]["pa"] == 2
    assert d["counts"]["runnerOutsOnPA"] == 1  # Literal '0' is not an out.
    assert d["counts"]["nonPAOuts"] == 1
    assert d["counts"]["sf"] == d["counts"]["cs2"] == 1
    assert d["expectedGDP"] == pytest.approx(0.2)
