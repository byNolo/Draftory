"""M9B.1 frozen old/new measurements; no tuning and no historical-output writes."""

import argparse
import gzip
import json
import subprocess
from statistics import mean, median

from .accuracy_audit import estimate, season_summary, without_trace_observations
from .calibration import analyze, write
from .runner_transitions import upgrade
from .source import digest
from .valuation import ROOT

WORK = ROOT / "data/processed/m9b1/measurements"


def run(binary, *args):
    return subprocess.run(
        [str(ROOT / f"target/release/examples/{binary}.exe"), *map(str, args)],
        check=True,
        capture_output=True,
        timeout=600,
    ).stdout


def collect(execute=False, benchmark=False):
    WORK.mkdir(parents=True, exist_ok=True)
    report_path = ROOT / "data/validation/runner-transitions-v1.json"
    previous = (
        json.loads(report_path.read_text("utf-8")) if report_path.exists() and not execute else {}
    )
    experiment_runner_sha = previous.get(
        "runnerSha256", digest(ROOT / "target/release/examples/audit_accuracy.exe")
    )
    fixture = json.loads((ROOT / "data/fixtures/runner-season-2024-v1.json").read_text("utf-8"))
    model = fixture["config"]["contextualModel"]
    baselines = {}
    targets = json.loads((ROOT / "data/processed/m4/targets.json").read_text("utf-8"))
    for year in (2022, 2023, 2024):
        old = json.loads((ROOT / f"data/processed/m4/inputs-{year}.json").read_text("utf-8"))
        baselines[str(year)] = {}
        for mode, inputs in (("old", old), ("new", [upgrade(i, model) for i in old])):
            path = WORK / f"inputs-{year}-{mode}.json"
            write(path, inputs)
            dest = WORK / f"rows-{year}-{mode}.json"
            if execute:
                raw = run("calibrate", path, 10, "contextual")
                write(dest, [json.loads(line) for line in raw.splitlines()])
            rows = json.loads(dest.read_text("utf-8"))
            if len(rows) != 300 or len({(r["teamId"], r["repeat"]) for r in rows}) != 300:
                raise ValueError("Incomplete historical experiment")
            result = analyze(rows, targets[str(year)])
            result["extended"] = {
                field: estimate(
                    [
                        sum(r["totals"].get(field, 0) for r in rows if r["repeat"] == rep) / 4860
                        for rep in range(10)
                    ]
                )
                for field in (
                    "groundedIntoDoublePlays",
                    "runsBattedIn",
                    "reachedOnError",
                    "fieldersChoices",
                )
            }
            baselines[str(year)][mode] = result
    roster_inputs = json.loads(
        (ROOT / "data/processed/m9a/nine-opponent-inputs.json").read_text("utf-8")
    )
    seasons, rows_by_mode = {}, {}
    for mode, inputs in (
        ("old", roster_inputs),
        ("new", [upgrade(i, model) for i in roster_inputs]),
    ):
        path = WORK / f"nine-{mode}.json"
        write(path, inputs)
        dest = WORK / f"nine-{mode}.jsonl"
        if execute:
            dest.write_bytes(run("audit_accuracy", path, 100, 20, 20261029))
        rows = [json.loads(line) for line in dest.read_bytes().splitlines()]
        if len(rows) != 300 or len({(r["team"], r["repeat"]) for r in rows}) != 300:
            raise ValueError("Incomplete roster experiment")
        rows_by_mode[mode] = rows
        seasons[mode] = season_summary(rows)
        for team, report in seasons[mode].items():
            selected = [r for r in rows if r["team"] == team and r["repeat"] < 20]
            report["runnerMetricsPerTraceSeason"] = [
                estimate([r["runnerMetrics"][k] for r in selected]) for k in range(3)
            ]
            report["rbiPerGame"] = mean(
                r["totals"]["runsBattedIn"] / 162 for r in rows if r["team"] == team
            )
    paired = {}
    for team in seasons["old"]:
        a = sorted((r for r in rows_by_mode["old"] if r["team"] == team), key=lambda r: r["repeat"])
        b = sorted((r for r in rows_by_mode["new"] if r["team"] == team), key=lambda r: r["repeat"])
        paired[team] = {
            field: estimate(
                [
                    (y["totals"].get(field, 0) - x["totals"].get(field, 0)) / 162
                    for x, y in zip(a, b, strict=True)
                ]
            )
            for field in (
                "plateAppearances",
                "hits",
                "runs",
                "runsBattedIn",
                "groundedIntoDoublePlays",
            )
        }
    probes = {}
    for mode in ("old", "new"):
        path = WORK / f"nine-{mode}.json"
        first = run("audit_accuracy", path, 2, 2, 20261029)
        assert first == run("audit_accuracy", path, 2, 2, 20261029)
        a = [json.loads(line) for line in first.splitlines()]
        b = [json.loads(line) for line in run("audit_accuracy", path, 2, 0, 20261029).splitlines()]
        for x, y in zip(a, b, strict=True):
            assert without_trace_observations(x) == without_trace_observations(y)
        probes[mode] = "six seasons repeat exactly; summary/events agree"
    nine_control = json.loads(
        (ROOT / "data/fixtures/dashboard-season-2024-v1.json").read_text("utf-8")
    )
    write(WORK / "benchmark-old-nine.json", nine_control)
    write(WORK / "benchmark-new-nine.json", upgrade(nine_control, model))
    performance_inputs = (
        ("old", ROOT / "crates/baseball-sim/tests/fixtures/season-modern-2024.json"),
        ("new", ROOT / "data/fixtures/runner-season-2024-v1.json"),
        ("old-nine", WORK / "benchmark-old-nine.json"),
        ("new-nine", WORK / "benchmark-new-nine.json"),
    )
    sizes = {}
    for mode, path in performance_inputs:
        value = json.loads(path.read_text("utf-8"))
        raw = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()
        context = json.dumps(
            value["config"]["contextualModel"], separators=(",", ":"), ensure_ascii=False
        ).encode()
        sizes[mode] = {
            "inputBytes": len(raw),
            "inputGzipBytes": len(gzip.compress(raw, mtime=0)),
            "modelBytes": len(context),
            "modelGzipBytes": len(gzip.compress(context, mtime=0)),
        }
    bench_path = WORK / "native-performance.json"
    if benchmark:
        bench = {}
        for mode, path in performance_inputs:
            bench[mode] = json.loads(run("measure_season", path, 100, "summary"))
        write(bench_path, bench)
    browser = {}
    for path in sorted((ROOT / "target/m9b1").glob("browser-*.json")):
        samples = json.loads(path.read_text("utf-8"))
        browser[path.stem.removeprefix("browser-")] = {
            sample["mode"]: {
                "samples": sample["runs"],
                "inputBytes": sample["inputBytes"],
                "warmSimulationMedianMs": median(r["simulationMs"] for r in sample["runs"][1:]),
                "warmWasmCallMedianMs": median(r["wasmCallMs"] for r in sample["runs"][1:]),
                "firstSimulationMs": sample["runs"][0]["simulationMs"],
                "compactJsonBytes": sample["runs"][0]["resultJsonBytes"],
                "compactCallMaxWasmMemoryBytes": max(
                    r["wasmMemoryAfterBytes"] for r in sample["runs"]
                ),
                "measurementFileSha256": digest(path),
            }
            for sample in samples
        }
    output = {
        "schemaVersion": "1.0.0",
        "engineVersion": "0.4.0",
        "modelId": model["id"],
        "trainingYears": [2022, 2023],
        "developmentYears": [2024],
        "newConfirmation": None,
        "historicalRepetitions": 10,
        "rosterRepetitions": 100,
        "traceRepetitions": 20,
        "runnerMetricOrder": ["tagOuts", "extraBatterBases", "existingRunnerAdvanceBases"],
        "runnerMetricWindow": (
            "user innings 1-8, joint single/double/residual contacts; "
            "safe advances exclude terminal and walkoff plays"
        ),
        "sourceAudit": json.loads(
            (ROOT / "data/processed/m9b1/verified/source-audit.json").read_text("utf-8")
        ),
        "baselines": baselines,
        "seasons": seasons,
        "pairedDifferences": paired,
        "reproducibility": probes,
        "sizes": sizes,
        "nativePerformance": json.loads(bench_path.read_text("utf-8"))
        if bench_path.exists()
        else None,
        "browserPerformance": browser,
        "artifacts": {
            str(p.relative_to(ROOT)): digest(p) for p in sorted(WORK.iterdir()) if p.is_file()
        },
        "runnerSha256": experiment_runner_sha,
        "probeRunnerSha256": digest(ROOT / "target/release/examples/audit_accuracy.exe"),
    }
    write(ROOT / "data/validation/runner-transitions-v1.json", output)
    print("M9B.1 measurements written")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--measure-native", action="store_true")
    args = parser.parse_args()
    collect(args.run, args.measure_native)


if __name__ == "__main__":
    main()
