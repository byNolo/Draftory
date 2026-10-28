"""Focused M8C.4 development comparison; no fitting, source mutation or deployment."""

import argparse
import gzip
import json
import math
import subprocess
from collections import Counter
from copy import deepcopy
from pathlib import Path
from statistics import mean, stdev

from .defense_research import distribution
from .source import canonical_bytes, digest
from .valuation import ROOT


def variants(real):
    neutral = deepcopy(real)
    for p in neutral["config"]["defense"]["assignments"]:
        p["errorRatio"] = 1_000_000
    legacy = deepcopy(neutral)
    legacy["config"].pop("defense")
    legacy.update(
        schemaVersion="1.0.0", gameSchemaVersion="1.2.0", rulesVersion="contextual-nine-inning-v1"
    )
    result = {"legacy": legacy, "neutral": neutral, "real": deepcopy(real)}
    for label, ratio in (("strong", 500_000), ("weak", 1_500_000)):
        value = deepcopy(real)
        for p in value["config"]["defense"]["assignments"]:
            if p["status"] == "observed":
                p["errorRatio"] = ratio
                p["id"] = f"control-{label}:{p['playerId']}:{p['position']}"
        result[label] = value
    return result


def observations(result):
    out = {k: result[k] for k in ("wins", "losses", "runsScored", "runsAllowed")}
    for label, stats in (
        ("user", result["team"]["totals"]),
        ("opponent", result["opponentTotals"]),
    ):
        for key in ("plateAppearances", "hits", "reachedOnError", "groundedIntoDoublePlays"):
            out[label + ":" + key] = stats.get(key, 0)
    cells = Counter()
    ordinary = 0
    model = result["input"]["config"]["contextualModel"]
    for game in result["games"]:
        outs, mask = 0, 0
        for play in game["eventLog"]:
            opponent_batting = (play["half"] == "top") == game["userHome"]
            if opponent_batting:
                cells[f"{outs}/{mask}"] += 1
                if play["suppliedEvent"]["kind"] == "otherContact":
                    transition = model["cells"][48 + outs * 8 + mask]["choices"][
                        play["transitionIndex"]
                    ]
                    ordinary += transition.get("reach") is None and play["outsOnPlay"] == 1
            after = play["stateAfter"]
            outs = after["outs"]
            mask = sum(1 << i for i, r in enumerate(after["bases"]) if r is not None)
    out["opponent:ordinaryContactOuts"] = ordinary
    return out, dict(sorted(cells.items()))


def compare(runner, output, repeats=64):
    if not 2 <= repeats <= 100:
        raise ValueError("Use 2..100 paired season seeds")
    fixture = ROOT / "data/fixtures/defense-season-2024-v1.json"
    modes = variants(json.loads(fixture.read_text("utf-8")))
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for seed in range(repeats):
        legacy_games = None
        for mode, template in modes.items():
            value = deepcopy(template)
            value.update(seed=str(seed), detail="events")
            path = output / f"input-{mode}-{seed}.json"
            path.write_bytes(canonical_bytes(value) + b"\n")
            run = subprocess.run(
                [str(runner.resolve()), str(path.resolve())],
                check=True,
                capture_output=True,
                timeout=60,
            )
            result = json.loads(run.stdout)
            if mode == "legacy":
                legacy_games = result["games"]
            if mode == "neutral" and result["games"] != legacy_games:
                raise ValueError("Neutral defense changed a legacy event")
            counters, cells = observations(result)
            rows.append(
                {
                    "mode": mode,
                    "seed": str(seed),
                    "inputSha256": digest(path),
                    "resultBytes": len(run.stdout),
                    "metrics": counters,
                    "baseOut": cells,
                }
            )
    metrics = list(rows[0]["metrics"])
    summary = {}
    for mode in modes:
        selected = [r for r in rows if r["mode"] == mode]
        pairs = [r for r in rows if r["mode"] == "legacy"]
        changes = {}
        for metric in metrics:
            delta = [
                r["metrics"][metric] - b["metrics"][metric]
                for r, b in zip(selected, pairs, strict=True)
            ]
            changes[metric] = {
                "mean": mean(delta),
                "mc95HalfWidth": 1.96 * stdev(delta) / math.sqrt(repeats),
            }
        summary[mode] = {
            "means": {k: mean(r["metrics"][k] for r in selected) for k in metrics},
            "pairedChangeFromLegacy": changes,
        }
    report = {
        "schemaVersion": "1.0.0",
        "fixtureSha256": digest(fixture),
        "runnerSha256": digest(runner),
        "seeds": repeats,
        "modes": summary,
    }
    (output / "observations.json").write_bytes(canonical_bytes(rows) + b"\n")
    return report


def collect_performance():
    native = json.loads((ROOT / "target/m8c4/native-performance.json").read_text("utf-8-sig"))
    result = {
        "schemaVersion": "1.0.0",
        "assetGzipLevel": 6,
        "nativePreparationMs": native["preparationSecondsPerMatchup"] * 1000,
        "native": [],
        "browsers": {},
        "assets": [],
    }
    for row in native["rows"]:
        result["native"].append(
            {
                "mode": row["mode"],
                "firstSeasonMs": row["seconds"][0] * 1000,
                "warmSeasonMs": distribution(x * 1000 for x in row["seconds"][1:]),
                "fullSummaryResultBytes": row["resultBytes"],
            }
        )
    for browser in ("chromium", "firefox", "webkit", "edge", "mobile-chromium", "mobile-webkit"):
        path = ROOT / f"target/m8c4/browser-{browser}.json"
        data = json.loads(path.read_text("utf-8"))
        result["browsers"][browser] = [
            {
                "mode": r["mode"],
                "inputBytes": r["inputBytes"],
                "initializationMs": r["initialization"].get("initializationMs"),
                "first": r["timings"][0],
                "warm": {
                    k: distribution(t[k] for t in r["timings"][1:])
                    for k in (
                        "simulationMs",
                        "wasmCallMs",
                        "inputParsingMs",
                        "serializationMs",
                        "resultProcessingMs",
                        "workerTotalMs",
                    )
                },
                "wasmLinearMemoryMaxBytes": max(t["wasmMemoryAfterBytes"] for t in r["timings"]),
            }
            for r in data
        ]
    for p in sorted((ROOT / "apps/web/dist/assets").iterdir()):
        if p.suffix in (".wasm", ".js") or p.name.startswith("defense-"):
            data = p.read_bytes()
            result["assets"].append(
                {
                    "file": p.name,
                    "bytes": len(data),
                    "gzipBytes": len(gzip.compress(data, compresslevel=6, mtime=0)),
                    "sha256": digest(p),
                }
            )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", type=Path)
    parser.add_argument("--collect-performance", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/processed/m8c4-validation")
    parser.add_argument("--repetitions", type=int, default=64)
    parser.add_argument(
        "--report", type=Path, default=ROOT / "data/validation/defense-v1-outcomes.json"
    )
    args = parser.parse_args()
    if args.collect_performance:
        target = ROOT / "data/validation/defense-v1-performance.json"
        target.write_bytes(canonical_bytes(collect_performance()) + b"\n")
        print(target)
        return
    if args.runner is None:
        parser.error("--runner is required for outcome comparisons")
    result = compare(args.runner, args.output_dir, args.repetitions)
    args.report.write_bytes(canonical_bytes(result) + b"\n")
    print(json.dumps(result["modes"], indent=2))


if __name__ == "__main__":
    main()
