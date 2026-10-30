"""M9A read-only model diagnostics. Never fits, publishes, or rewrites inputs."""

import argparse
import json
import math
import subprocess
from collections import Counter, defaultdict
from statistics import mean, stdev, variance

from . import retrosheet
from .calibration import write
from .defense import verify_dev
from .defense_research import contact_event, play_flags
from .source import DataError, digest, verify_source
from .transitions import supported_transition
from .valuation import ROOT

WORK = ROOT / "data/processed/m9a"
METRICS = {
    "runs": "runs",
    "hits": "hits",
    "pa": "plateAppearances",
    "walks": "walks",
    "strikeouts": "strikeouts",
    "double": "doubles",
    "triple": "triples",
    "homeRuns": "homeRuns",
    "gdp": "groundedIntoDoublePlays",
    "hbp": "hitByPitch",
}


def estimate(samples):
    n = len(samples)
    return {
        "mean": mean(samples),
        "sd": stdev(samples) if n > 1 else 0,
        "mc95HalfWidth": 1.96 * stdev(samples) / math.sqrt(n) if n > 1 else None,
        "n": n,
    }


def without_trace_observations(row):
    """Compare outcomes across detail modes, including older native audit runners."""
    return {
        k: v
        for k, v in row.items()
        if k not in ("traceCells", "expectedGDP", "inningPA", "runnerMetrics")
    }


def decomposition(hist_pa, hist_h, sim_pa, sim_h):
    """Exact additive identity, descriptive rather than a causal ablation."""
    volume = (sim_pa - hist_pa) * hist_h / hist_pa
    rate = sim_pa * (sim_h / sim_pa - hist_h / hist_pa)
    return {"volume": volume, "rate": rate, "total": sim_h - hist_h}


def preparation_differences(new, old, path=""):
    """Retain old diagnostic names; permit only proven reversible UTF-8 mojibake."""
    if new == old:
        return []
    if isinstance(new, dict) and isinstance(old, dict) and new.keys() == old.keys():
        return [d for k in new for d in preparation_differences(new[k], old[k], f"{path}/{k}")]
    if isinstance(new, list) and isinstance(old, list) and len(new) == len(old):
        return [
            d
            for i, (a, b) in enumerate(zip(new, old, strict=True))
            for d in preparation_differences(a, b, f"{path}/{i}")
        ]
    if path.endswith("/displayName") and isinstance(old, str):
        corrected = old
        for _ in range(2):
            try:
                corrected = corrected.encode("cp1252").decode("utf-8")
            except UnicodeError:
                break
            if corrected == new:
                return [{"path": path, "regenerated": new, "archived": old}]
    raise DataError(f"Unexpected preparation difference at {path}")


def gdp_factors(cells):
    pa, contact, gdp = (sum(c) for c in cells)
    eligible = sum(cells[1][o * 8 + b] for o in (0, 1) for b in (1, 3, 5, 7))
    state = sum(cells[0][o * 8 + b] for o in (0, 1) for b in (1, 3, 5, 7))
    return {
        "pa": pa,
        "contact": contact,
        "eligible": eligible,
        "gdp": gdp,
        "stateEligiblePerPA": state / pa,
        "contactPerPA": contact / pa,
        "eligiblePerContact": eligible / contact,
        "gdpPerEligible": gdp / eligible,
        "gdpPerPA": gdp / pa,
    }


def source_plays(year, directory):
    counts, types, reasons, inning_pa = Counter(), Counter(), Counter(), Counter()
    dpopp_mismatches, contact_types = Counter(), Counter()
    cells = [[0] * 24 for _ in range(3)]
    halves = defaultdict(int)
    model = json.loads((WORK / "prepared/transitions.json").read_text("utf-8"))
    table = {(c["outs"], c["baseMask"]): c for c in model["cells"] if c["event"] == "otherContact"}
    expected = 0
    for row in retrosheet.zip_rows(directory, f"{year}plays.zip", f"{year}plays.csv", headers=True):
        if row["gametype"] != "regular" or row["pbp"] != "full" or int(row["inning"]) > 8:
            continue
        pa = row["pa"] == "1"
        counts["rows"] += 1
        counts["paIncludingSacrifices"] += pa
        for key in (
            "sh",
            "sf",
            "sb2",
            "sb3",
            "sbh",
            "cs2",
            "cs3",
            "csh",
            "pko1",
            "pko2",
            "pko3",
            "wp",
            "pb",
            "bk",
            "othdp",
            "tp",
            "k_safe",
        ):
            counts[key] += int(row[key])
        delta = int(row["outs_post"]) - int(row["outs_pre"])
        counts["nonPAOuts"] += delta if not pa else 0
        counts["runnerOutsOnPA"] += (
            sum(row[f"brout{i}"] not in ("", "0") for i in range(1, 4)) if pa else 0
        )
        if pa:
            halves[row["gid"], row["inning"], row["top_bot"]] += 1
        # Match the frozen fitter exactly; totals above retain omitted-event evidence.
        if not pa or row["sh"] != "0" or row["sf"] != "0":
            continue
        outs, mask, opp = play_flags(row)
        event = contact_event(row)
        cells[0][outs * 8 + mask] += 1
        counts["roe"] += int(row["roe"])
        counts["dpopp"] += int(row["dpopp"])
        counts["eligibleGround"] += opp and row["ground"] == "1"
        counts["eligibleResidualGround"] += opp and event == "otherContact" and row["ground"] == "1"
        residual_ground = opp and event == "otherContact" and row["ground"] == "1"
        if (row["dpopp"] == "1") != residual_ground:
            dpopp_mismatches[
                f"flag{row['dpopp']}:{event or 'otherPA'}:{row['hittype'] or 'unknown'}"
            ] += 1
        if row["bip"] == "1":
            types[row["hittype"] or "unknown"] += 1
            contact_types[f"{row['hittype'] or 'unknown'}:{event or 'otherPA'}"] += 1
        if event:
            _, reason = supported_transition(row, event, outs, mask)
            reasons[reason] += 1
        if event == "otherContact":
            cells[1][outs * 8 + mask] += 1
            cells[2][outs * 8 + mask] += int(row["gdp"])
            if opp:
                expected += sum(
                    c["weight"]
                    for c in table[outs, mask]["choices"]
                    if c["destinations"][0] == 0 and c["destinations"][1] == 0
                )
    for n in halves.values():
        inning_pa[n] += 1
    return {
        "counts": dict(counts),
        "hitTypes": dict(types),
        "hitTypesByEvent": dict(contact_types),
        "dpoppResidualGroundMismatches": dict(dpopp_mismatches),
        "reasons": dict(reasons),
        "cells": cells,
        "factors": gdp_factors(cells),
        "expectedGDP": expected / 1e6,
        "inningPA": dict(sorted(inning_pa.items())),
        "playedHalves": len(halves),
        "paPerHalf": sum(n * f for n, f in inning_pa.items()) / len(halves),
    }


def historical_baseline():
    report = {}
    for year in (2022, 2023, 2024, 2025):
        logs = retrosheet.game_logs(ROOT / "data/raw/retrosheet-m4", year)
        rows = json.loads((WORK / f"calibration/rows-{year}-contextual.json").read_text("utf-8"))
        historical = {k: mean(t["stats"][k] for g in logs for t in g["teams"]) for k in METRICS}
        simulated = {}
        for metric, field in METRICS.items():
            samples = [
                sum(r["totals"].get(field, 0) for r in rows if r["repeat"] == rep)
                / sum(r["games"] for r in rows if r["repeat"] == rep)
                for rep in range(20)
            ]
            simulated[metric] = estimate(samples)
        repeats = []
        for rep in range(20):
            selected = [r for r in rows if r["repeat"] == rep]
            histogram = Counter()
            for r in selected:
                histogram.update({int(k): v for k, v in r["scoreHistogram"].items()})
            n = sum(histogram.values())
            avg = sum(k * v for k, v in histogram.items()) / n
            repeats.append(
                {
                    "shutouts": histogram[0] / n,
                    "tenPlus": sum(v for k, v in histogram.items() if k >= 10) / n,
                    "runSD": math.sqrt(
                        sum(v * (k - avg) ** 2 for k, v in histogram.items()) / (n - 1)
                    ),
                    "extras": sum(r["extraInningGames"] for r in selected) / n,
                }
            )
        scores = [t["stats"]["runs"] for g in logs for t in g["teams"]]
        old = ROOT / f"data/processed/m4/results/rows-{year}-contextual.json"
        old_rows = json.loads(old.read_text("utf-8"))

        def strip(rs):
            return [{k: v for k, v in r.items() if k != "seasonSeconds"} for r in rs]

        if strip(rows) != strip(old_rows):
            raise DataError(f"Current engine differs from archived contextual rows: {year}")
        base_rows = json.loads((WORK / f"calibration/rows-{year}-baseline.json").read_text("utf-8"))
        old_base = json.loads(
            (ROOT / f"data/processed/m4/results/rows-{year}-baseline.json").read_text("utf-8")
        )
        if strip(base_rows) != strip(old_base):
            raise DataError(f"Current engine differs from archived baseline rows: {year}")
        report[str(year)] = {
            "historical": historical,
            "simulated": simulated,
            "historicalDistribution": {
                "shutouts": scores.count(0) / len(scores),
                "tenPlus": sum(s >= 10 for s in scores) / len(scores),
                "runSD": stdev(scores),
                "extras": sum(max(len(t["lineScore"]) for t in g["teams"]) > 9 for g in logs)
                / len(logs),
                "beyondTen": sum(max(len(t["lineScore"]) for t in g["teams"]) > 10 for g in logs)
                / len(logs),
                "meanInnings": mean(max(len(t["lineScore"]) for t in g["teams"]) for g in logs),
            },
            "simulatedContactRates": {
                field: estimate(
                    [
                        sum(r["totals"].get(field, 0) for r in rows if r["repeat"] == rep)
                        / sum(r["games"] for r in rows if r["repeat"] == rep)
                        for rep in range(20)
                    ]
                )
                for field in ("reachedOnError", "fieldersChoices")
            },
            "simulatedDistribution": {k: estimate([r[k] for r in repeats]) for k in repeats[0]},
            "hitDifference": decomposition(
                historical["pa"],
                historical["hits"],
                simulated["pa"]["mean"],
                simulated["hits"]["mean"],
            ),
            "archivedRowsIdenticalExcludingTimings": True,
        }
    return report


def roster_rates():
    lineups = json.loads((WORK / "prepared/lineups.json").read_text("utf-8"))
    result = {}
    for year in (2022, 2023, 2024):
        rows = [r for r in lineups if r["season"] == year]
        h = [p["basePreparation"] for r in rows for p in r["profiles"]]
        result[str(year)] = {
            "selectedPA": sum(p["historicalProfile"]["opportunities"] for p in h),
            "equalSlotRawUnconditionalHitRate": mean(
                sum(
                    p["historicalProfile"]["probabilities"][k]
                    for k in ("single", "double", "triple", "homeRun")
                )
                for p in h
            ),
            "equalSlotRawConditionalHitRate": mean(
                sum(p["mappedProbabilities"][k] for k in ("single", "double", "triple", "homeRun"))
                for p in h
            ),
            "equalSlotSmoothedHitRate": mean(
                sum(
                    p["smoothedProbabilities"][k] for k in ("single", "double", "triple", "homeRun")
                )
                for p in h
            ),
            "equalSlotSacrificeMass": mean(p["mapping"]["excludedSacrificeMass"] for p in h),
        }
    return result


def make_rosters():
    publication = json.loads((ROOT / "data/publications/opponents-2024-v1.json").read_text("utf-8"))
    # Verify immutable published bytes against its canonical content ID.
    from .simulation import identity

    if publication["id"] != identity(
        {k: v for k, v in publication.items() if k != "id"}, "opponents"
    ):
        raise DataError("Opponent publication content mismatch")
    template = json.loads((ROOT / "data/fixtures/dashboard-season-2024-v1.json").read_text("utf-8"))
    if template["config"].get("defense"):
        raise DataError("Audit baseline must be neutral")
    inputs = []
    for code in ("CHA", "HOU", "NYA"):
        source = next(t for t in publication["opponents"] if t["sourceTeamId"] == code)
        team = {
            "id": f"audit:2024:{code}",
            "lineup": [
                {"id": f"audit:{code}:{b['playerId']}", "profileId": b["profileId"]}
                for b in source["lineup"]
            ],
        }
        inputs.append(
            {
                **template,
                "userTeam": team,
                "profiles": publication["profiles"],
                "userLineupKind": "synthetic",
                "opponentSetKind": "synthetic",
                "opponents": [
                    {
                        "id": t["id"],
                        "lineup": [
                            {"id": b["id"], "profileId": b["profileId"]} for b in t["lineup"]
                        ],
                    }
                    for t in publication["opponents"]
                ],
            }
        )
    write(WORK / "nine-opponent-inputs.json", inputs)
    return inputs


def run_native(runner, inputs, repeats, traces, base):
    return subprocess.run(
        [str(runner), str(inputs), str(repeats), str(traces), str(base)],
        check=True,
        capture_output=True,
        timeout=600,
    ).stdout


def season_summary(rows):
    result = {}
    for team in sorted({r["team"] for r in rows}):
        selected = [r for r in rows if r["team"] == team]
        wins = [r["wins"] for r in selected]
        games = [g for r in selected for g in r["games"]]
        n = len(selected)
        by_slot = [[r["games"][j] for r in selected] for j in range(162)]
        ps = [mean(g["won"] for g in slot) for slot in by_slot]
        # Unbiased estimate of sum p_j(1-p_j) from n season replications per fixed game slot.
        pb_variance = sum(p * (1 - p) * n / (n - 1) for p in ps)
        scores = [g["score"][0] for g in games]

        def half(g, line):
            return line["home"] if g["home"] else line["away"]

        cells = [
            [sum(r["traceCells"][k][j] for r in selected) for j in range(24)] for k in range(3)
        ]
        hist = Counter()
        for r in selected:
            hist.update({int(k): v for k, v in r["inningPA"].items()})
        per_half = sum(k * v for k, v in hist.items()) / sum(hist.values())
        ordered = sorted(wins)
        residuals = [sum(g["won"] - ps[j] for j, g in enumerate(r["games"][:81])) for r in selected]
        later = [
            sum(g["won"] - ps[j + 81] for j, g in enumerate(r["games"][81:])) for r in selected
        ]
        covariance = sum(
            (a - mean(residuals)) * (b - mean(later)) for a, b in zip(residuals, later, strict=True)
        ) / (n - 1)
        result[team] = {
            "seeds": n,
            "wins": estimate(wins),
            "winMinMax": [min(wins), max(wins)],
            "winEmpirical95": [ordered[int(0.025 * n)], ordered[int(0.975 * n) - 1]],
            "wins70OrBelow": sum(w <= 70 for w in wins) / n,
            "wins93OrAbove": sum(w >= 93 for w in wins) / n,
            "outsideTwoBaselineSD": sum(
                abs(w - mean(wins)) > 2 * math.sqrt(pb_variance) for w in wins
            )
            / n,
            "poissonBinomialSD": math.sqrt(pb_variance),
            "winVarianceRatio": variance(wins) / pb_variance,
            "firstSecondHalfResidualCovariance": covariance,
            "rs": estimate([r["rs"] for r in selected]),
            "ra": estimate([r["ra"] for r in selected]),
            "rd": estimate([r["rs"] - r["ra"] for r in selected]),
            "gameRunSD": stdev(scores),
            "shutouts": scores.count(0) / len(scores),
            "tenPlus": sum(s >= 10 for s in scores) / len(scores),
            "extras": sum(g["innings"] > 9 for g in games) / len(games),
            "extraBeyondTen": sum(g["innings"] > 10 for g in games) / len(games),
            "meanInnings": mean(g["innings"] for g in games),
            "scoreHistogram": dict(sorted(Counter(scores).items())),
            "totalsPerGame": {
                field: mean(g["totals"].get(field, 0) for g in games) for field in METRICS.values()
            },
            "outsPerGame": mean(g["outs"] for g in games),
            "lobPerGame": mean(g["lob"] for g in games),
            "playedUserHalvesPerGame": mean(
                sum(half(g, line) is not None for line in g["lines"]) for g in games
            ),
            "trace": {
                "cells": cells,
                "factors": gdp_factors(cells),
                "expectedGDP": sum(r["expectedGDP"] for r in selected),
                "inningPA": dict(sorted(hist.items())),
                "paPerHalf": per_half,
                "tenPlusPAHalfRate": sum(v for k, v in hist.items() if k >= 10)
                / sum(hist.values()),
            },
            "expectedOutcomesPerGame": {
                k: sum(r["expectedOutcomes"][k] for r in selected) / len(games)
                for k in selected[0]["expectedOutcomes"]
            },
            "samplingResidualPerGame": {
                event: estimate(
                    [(r["totals"][field] - r["expectedOutcomes"][event]) / 162 for r in selected]
                )
                for event, field in (
                    ("double", "doubles"),
                    ("triple", "triples"),
                    ("homeRun", "homeRuns"),
                    ("walk", "walks"),
                    ("hitByPitch", "hitByPitch"),
                    ("strikeout", "strikeouts"),
                )
            },
        }
        for r in selected:
            for g in r["games"]:
                if g["totals"]["plateAppearances"] != g["outs"] + g["lob"] + g["score"][0]:
                    raise DataError("Runner conservation failure")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-native", action="store_true")
    args = parser.parse_args()
    runner = ROOT / "target/release/examples/audit_accuracy.exe"
    source = verify_source(ROOT / "data/raw/lahman-2025")
    retro = retrosheet.verify(ROOT / "data/raw/retrosheet-m4")
    dev = verify_dev(ROOT / "data/raw/retrosheet-defense-2024")
    make_rosters()
    path = WORK / "nine-opponent-inputs.json"
    if args.run_native:
        (WORK / "season-rows.jsonl").write_bytes(run_native(runner, path, 200, 20, 20261029))
    rows = [json.loads(line) for line in (WORK / "season-rows.jsonl").read_bytes().splitlines()]
    if len(rows) != 600 or len({(r["team"], r["repeat"]) for r in rows}) != 600:
        raise DataError("Missing or duplicated season rows")
    first = run_native(runner, path, 2, 2, 20261029)
    second = run_native(runner, path, 2, 2, 20261029)
    if first != second:
        raise DataError("Identical seeds did not reproduce bytes")
    summary = [json.loads(line) for line in run_native(runner, path, 2, 0, 20261029).splitlines()]
    for a, b in zip([json.loads(line) for line in first.splitlines()], summary, strict=True):
        if without_trace_observations(a) != without_trace_observations(b):
            raise DataError("Event logging changes outcomes")
    prepared = WORK / "prepared"
    files = sorted(p.name for p in prepared.iterdir())
    parity = {
        name: digest(prepared / name) == digest(ROOT / "data/processed/m4" / name) for name in files
    }
    differences = {}
    for name, equal in parity.items():
        if not equal:
            differences[name] = preparation_differences(
                json.loads((prepared / name).read_text("utf-8")),
                json.loads((ROOT / "data/processed/m4" / name).read_text("utf-8")),
            )
    report = {
        "schemaVersion": "1.0.0",
        "auditVersion": "m9a-accuracy-v1",
        "sourceCommit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source": source,
        "retrosheet": retro,
        "devArchiveSha256": dev["sha256"],
        "runnerSha256": digest(runner),
        "seasonInputSha256": digest(path),
        "seasonRowsSha256": digest(WORK / "season-rows.jsonl"),
        "split": {
            "training": [2022, 2023],
            "development": [2024],
            "previouslyInspectedDiagnosticOnly": [2025],
            "newConfirmation": None,
        },
        "preparationByteParity": parity,
        "preparationDiagnosticNameDifferences": differences,
        "baseline": historical_baseline(),
        "rosterRates": roster_rates(),
        "sourcePlays": {
            str(y): source_plays(
                y,
                ROOT
                / ("data/raw/retrosheet-defense-2024" if y == 2024 else "data/raw/retrosheet-m4"),
            )
            for y in (2022, 2023, 2024)
        },
        "seasons": season_summary(rows),
        "reproducibility": {
            "twoNativeRunsByteIdentical": True,
            "summaryEventsIdentical": True,
            "checkedSeasons": 6,
            "baseSeed": "20261029",
            "repetitions": 200,
            "traceRepetitions": 20,
            "runnerConservationAllGames": True,
        },
        "inputs": {
            str(p.relative_to(ROOT)): digest(p)
            for p in [
                ROOT / "data/publications/opponents-2024-v1.json",
                path,
                ROOT / "data/pipeline/src/draftory_data/resources/retrosheet-m4.lock.json",
                ROOT / "data/pipeline/src/draftory_data/resources/retrosheet-defense-dev.lock.json",
            ]
        },
    }
    write(ROOT / "data/validation/simulation-accuracy-v1.json", report)
    print("M9A audit measurements written; no simulation parameters changed.")


if __name__ == "__main__":
    main()
