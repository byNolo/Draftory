"""Source splits, empirical transitions, contracts and independent analysis math."""

import csv
import io
import json
import zipfile
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from draftory_data.calibration import (
    analyze,
    compatible_opponents,
    run,
    summarize_targets,
    total_variation,
)
from draftory_data.retrosheet import fetch, game_logs, line_score, source_lock, verify
from draftory_data.source import DataError, canonical_bytes
from draftory_data.transitions import conservative, fit_model, supported_transition

ROOT = Path(__file__).resolve().parents[3]
SCHEMAS = {
    p.stem.removesuffix(".schema"): json.loads(p.read_text("utf-8"))
    for p in (ROOT / "contracts").glob("*.schema.json")
}
REGISTRY = Registry().with_resources(
    (s["$id"], Resource.from_contents(s)) for s in SCHEMAS.values() if "$id" in s
)


def fixture():
    return json.loads(
        (ROOT / "crates/baseball-sim/tests/fixtures/season-modern-2024.json").read_text("utf-8")
    )


def validate(name, value):
    Draft202012Validator(SCHEMAS[name], registry=REGISTRY).validate(value)


def play(**updates):
    values = dict.fromkeys(
        (
            "wp",
            "pb",
            "bk",
            "sb2",
            "sb3",
            "sbh",
            "cs2",
            "cs3",
            "csh",
            "oa",
            "roe",
            "fc",
            "gdp",
            "othout",
            "rbi1",
            "rbi2",
            "rbi3",
        ),
        "0",
    )
    values.update(
        {
            k: ""
            for k in (
                "br1_pre",
                "br2_pre",
                "br3_pre",
                "br1_post",
                "br2_post",
                "br3_post",
                "run_b",
                "run1",
                "run2",
                "run3",
            )
        }
    )
    values.update(batter="batter", outs_post="0")
    return values | updates


def test_source_lock_has_official_urls_and_no_holdout_plays():
    lock = source_lock()
    assert lock["trainingYears"] == [2022, 2023]
    assert lock["developmentValidationYears"] == [2024]
    assert lock["holdoutYears"] == [2025]
    assert all(f["url"].startswith("https://www.retrosheet.org/") for f in lock["files"])
    assert {f["name"] for f in lock["files"] if "plays.zip" in f["name"]} == {
        "2022plays.zip",
        "2023plays.zip",
    }
    assert all(len(f["sha256"]) == 64 and f["sizeBytes"] > 0 for f in lock["files"])


def test_traded_player_stint_versions_cannot_oppose_themselves():
    user = {"id": "user", "lineup": [{"profileId": "first-stint"}]}
    traded = {"id": "traded", "lineup": [{"profileId": "second-stint"}]}
    other = {"id": "other", "lineup": [{"profileId": "other-player"}]}
    profiles = {
        key: {"provenance": {"playerId": pid}}
        for key, pid in [
            ("first-stint", "same-player"),
            ("second-stint", "same-player"),
            ("other-player", "different"),
        ]
    }
    available, excluded = compatible_opponents(user, [user, traded, other], profiles)
    assert available == [other]
    assert excluded == [{"teamId": "traded", "sharedPlayerIds": ["same-player"]}]


def test_tampered_cache_is_rejected_without_network_or_overwrite(tmp_path, monkeypatch):
    entry = {
        "name": "bad.zip",
        "sizeBytes": 3,
        "sha256": "0" * 64,
        "url": "https://www.retrosheet.org/bad",
    }
    monkeypatch.setattr("draftory_data.retrosheet.source_lock", lambda: {"files": [entry]})
    path = tmp_path / "bad.zip"
    path.write_bytes(b"bad")
    with pytest.raises(DataError, match="integrity"):
        verify(tmp_path)
    with pytest.raises(DataError, match="Changed cached"):
        fetch(tmp_path)
    assert path.read_bytes() == b"bad"


def test_empirical_hits_and_error_choice_categories_are_explicit():
    row = play(br2_pre="runner", br1_post="batter", run2="runner", rbi2="1", outs_post="1")
    transition, reason = supported_transition(row, "single", 1, 2)
    assert transition == ((1, 5, 4, 5), (False, False, True, False), "none")
    assert reason == "observed-safe-transition"
    row = play(roe="1", br1_post="batter")
    assert supported_transition(row, "otherContact", 0, 0)[0] == (
        (1, 5, 5, 5),
        (False,) * 4,
        "error",
    )
    row = play(fc="1", br1_pre="runner", br1_post="batter", outs_post="1")
    assert supported_transition(row, "otherContact", 0, 1)[0] == (
        (1, 0, 5, 5),
        (False,) * 4,
        "fieldersChoice",
    )


def test_double_play_and_third_out_proxies_cannot_create_force_play_runs():
    row = play(gdp="1", br1_pre="first", br3_pre="third", outs_post="3", run3="third")
    transition, reason = supported_transition(row, "otherContact", 1, 5)
    assert transition == ((0, 0, 5, 3), (False,) * 4, "none")
    assert reason == "ground-double-play"
    row = play(othout="1", br3_pre="third", outs_post="3")
    assert supported_transition(row, "otherContact", 2, 4)[0] == conservative("otherContact", 2, 4)


def test_running_out_on_hit_remains_an_audited_proxy():
    transition, reason = supported_transition(play(outs_post="1", br1_pre="runner"), "single", 0, 1)
    assert transition == conservative("single", 0, 1)
    assert reason == "running-out-on-hit-proxy"


def test_force_out_category_can_retire_a_runner_while_batter_reaches():
    row = play(othout="1", br1_pre="runner", br1_post="batter", outs_post="1")
    transition, reason = supported_transition(row, "otherContact", 0, 1)
    assert transition == ((1, 0, 5, 5), (False,) * 4, "fieldersChoice")
    assert reason == "observed-fieldersChoice"
    row = play(fc="1", br1_pre="runner", br1_post="batter", br2_post="runner")
    assert supported_transition(row, "otherContact", 0, 1)[0][2] == "fieldersChoice"


def test_line_scores_include_double_digit_innings_and_unplayed_halves():
    assert line_score("010(12)00x") == [0, 1, 0, 12, 0, 0, None]
    with pytest.raises(DataError):
        line_score("0?0")


def log_row():
    row = [""] * 161
    row[0] = "20220401"
    row[1] = "0"
    row[3] = "AAA"
    row[4] = "AL"
    row[6] = "BBB"
    row[7] = "NL"
    row[9] = "2"
    row[10] = "0"
    row[11] = "54"
    row[19] = "200000000"
    row[20] = "000000000"
    for start in (21, 49):
        row[start : start + 17] = ["0"] * 17
        row[start] = "27"
    row[22] = "2"
    row[26] = "2"
    for start, prefix in ((105, "a"), (132, "b")):
        for i in range(9):
            row[start + i * 3 : start + i * 3 + 3] = [f"{prefix}{i}", "Synthetic", "1"]
    return row


def write_logs(path, rows):
    stream = io.StringIO(newline="")
    csv.writer(stream).writerows(rows)
    with zipfile.ZipFile(path / "gl2022.zip", "w") as source:
        source.writestr("gl2022.txt", stream.getvalue())


def test_game_log_totals_targets_and_starters(tmp_path):
    write_logs(tmp_path, [log_row()])
    games = game_logs(tmp_path, 2022)
    assert games[0]["teams"][0]["stats"]["pa"] == 27
    assert len(set(games[0]["teams"][0]["lineup"])) == 9
    # Two independent games permit a descriptive standard-error calculation.
    targets = summarize_targets(games * 2)
    assert targets["metrics"]["runs"]["mean"] == 1
    assert targets["shutoutRate"] == 0.5
    assert targets["teams"]["AAA"]["wins"] == 2


@pytest.mark.parametrize("bad", ["duplicate", "missingStat", "badShape", "tied"])
def test_malformed_or_duplicate_game_logs_are_rejected(tmp_path, bad):
    row = log_row()
    rows = [row]
    if bad == "duplicate":
        rows.append(deepcopy(row))
    elif bad == "missingStat":
        row[22] = ""
    elif bad == "badShape":
        row.pop()
    else:
        row[10] = "2"
    write_logs(tmp_path, rows)
    with pytest.raises(DataError):
        game_logs(tmp_path, 2022)


def test_schemas_and_historical_season_fixture():
    for name in ("contextual-model", "season-input", "season-result", "season-batting-summary"):
        Draft202012Validator.check_schema(SCHEMAS[name])
    value = fixture()
    validate("season-input", value)
    model = value["config"]["contextualModel"]
    validate("contextual-model", model)
    assert len(model["cells"]) == 72
    assert all(sum(c["weight"] for c in cell["choices"]) == 1_000_000 for cell in model["cells"])
    ids = {p["id"]: p["provenance"]["playerId"] for p in value["profiles"]}
    for team in [value["userTeam"], *value["opponents"]]:
        assert len({ids[b["profileId"]] for b in team["lineup"]}) == 9
    game = {
        "schemaVersion": value["gameSchemaVersion"],
        "rulesVersion": value["rulesVersion"],
        **{
            k: value[k]
            for k in ("seed", "config", "detail", "pitchingEnvironment", "sampling", "profiles")
        },
        "teams": {"away": value["userTeam"], "home": value["opponents"][0]},
    }
    validate("simulation-input", game)
    game["profiles"][0]["weights"]["battedBallOut"] = 1
    with pytest.raises(ValidationError):
        validate("simulation-input", game)


def test_analysis_reports_between_repeat_variation_and_strength_groups():
    teams = {
        f"T{i:02}": {
            "games": 162,
            "wins": 81,
            "losses": 81,
            "totals": {"runs": 324 + i},
            "runsAllowed": 324,
        }
        for i in range(30)
    }
    target = {
        "metrics": {
            k: {"mean": 2} for k in ("runs", "hits", "walks", "strikeouts", "homeRuns", "pa")
        },
        "teams": teams,
    }
    rows = []
    for repeat in (0, 1):
        score = 1 + repeat * 2
        for team in teams:
            rows.append(
                {
                    "repeat": repeat,
                    "teamId": "2024." + team,
                    "games": 162,
                    "wins": 80 + repeat,
                    "losses": 82 - repeat,
                    "runsScored": score * 162,
                    "runsAllowed": 324,
                    "totals": dict.fromkeys(
                        ("runs", "hits", "walks", "strikeouts", "homeRuns", "plateAppearances"),
                        score * 162,
                    ),
                    "scoreHistogram": {str(score): 162},
                    "inningTotals": [[0, 162]] * 9,
                    "seasonSeconds": 0.01,
                }
            )
    result = analyze(rows, target)
    assert result["metrics"]["runs"]["simulated"] == 2
    assert result["metrics"]["runs"]["repeatSd"] > 1
    assert set(result["strengthGroups"]) == {"weak", "average", "strong"}
    assert result["runDifferentialWinRateCorrelation"] == pytest.approx(1)
    assert total_variation({"0": 1, "1": 1}, {1: 2}) == 0.5


def test_optional_official_transition_fit_is_reproducible(request):
    path = request.config.getoption("--retrosheet-source")
    if not path:
        pytest.skip("Provide --retrosheet-source for official calibration integration")
    directory = Path(path)
    model, audit = fit_model(directory)
    assert json.loads(canonical_bytes(model)) == fixture()["config"]["contextualModel"]
    assert audit["trainingYears"] == [2022, 2023]
    assert audit["holdoutYears"] == [2025]
    assert audit["classificationCounts"]["observed-error"] > 0
    assert audit["classificationCounts"]["observed-fieldersChoice"] > 0
    for year, games in ((2022, 2430), (2023, 2430), (2024, 2429), (2025, 2430)):
        assert len(game_logs(directory, year)) == games


def test_duplicate_native_batch_rows_are_not_accepted_as_repeated_seasons(tmp_path, monkeypatch):
    (tmp_path / "targets.json").write_text(
        json.dumps({"2022": {"teams": {f"T{i:02}": {} for i in range(30)}}})
    )
    monkeypatch.setattr("draftory_data.calibration.YEARS", (2022,))
    output = "\n".join(json.dumps({"repeat": 0, "teamId": "2022.T00"}) for _ in range(60))
    monkeypatch.setattr(
        "draftory_data.calibration.subprocess.run",
        lambda *a, **kw: SimpleNamespace(returncode=0, stdout=output, stderr=""),
    )
    with pytest.raises(DataError, match="duplicated"):
        run(tmp_path, tmp_path / "runner", 2, tmp_path / "output")
    assert not (tmp_path / "output/calibration.json").exists()


def test_compact_batting_contract_preserves_boxes_without_input_or_event_traces():
    golden = json.loads((ROOT / "data/fixtures/simulation-result.synthetic.json").read_text())
    box = golden["teams"][0]
    projection = {
        "schemaVersion": "1.0.0",
        "engineVersion": "0.4.0",
        "seed": "18446744073709551615",
        "games": 162,
        "wins": 81,
        "losses": 81,
        "runsScored": box["totals"]["runs"],
        "runsAllowed": 0,
        "runDifferential": box["totals"]["runs"],
        "batting": {
            "schemaVersion": "1.0.0",
            "teamId": box["teamId"],
            "totals": box["totals"],
            "batters": box["batters"],
        },
    }
    validate("season-batting-summary", projection)
    for field, value in (("input", {}), ("eventLog", []), ("seed", 123), ("games", 0)):
        invalid = {**projection, field: value}
        with pytest.raises(ValidationError):
            validate("season-batting-summary", invalid)
    projection["batting"]["batters"] = box["batters"][:8]
    with pytest.raises(ValidationError):
        validate("season-batting-summary", projection)
