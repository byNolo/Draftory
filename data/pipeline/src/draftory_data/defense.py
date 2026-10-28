"""M8C.4 versioned error-avoidance supplement; no batting or pricing changes."""

import argparse
import json
import math
from collections import Counter
from fractions import Fraction
from importlib.resources import files
from pathlib import Path
from urllib.request import urlopen

from . import retrosheet
from .defense_research import DATASET_ID, POSITIONS, aggregate_fielding, contact_event, play_flags
from .simulation import identity
from .source import DataError, canonical_bytes, digest, lock_digest, verify_source
from .tables import read_table
from .transitions import conservative, supported_transition
from .valuation import FIXTURE_SHA, ROOT, load_publication

SCALE = 1_000_000
VERSION = "error-avoidance-v1"
MIN_INNINGS = 100
PRIOR_CHANCES = 1000


def dev_lock():
    return json.loads(
        files("draftory_data")
        .joinpath("resources/retrosheet-defense-dev.lock.json")
        .read_text("utf-8")
    )


def verify_dev(directory):
    lock = dev_lock()
    path = directory / lock["path"]
    if (
        not path.exists()
        or path.stat().st_size != lock["sizeBytes"]
        or digest(path) != lock["sha256"]
    ):
        raise DataError("2024 development-play integrity mismatch; run fetch-dev explicitly")
    return lock


def fetch_dev(directory):
    lock = dev_lock()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / lock["path"]
    if not path.exists():
        part = path.with_suffix(".part")
        try:
            with urlopen(lock["url"], timeout=60) as response:
                part.write_bytes(response.read(lock["sizeBytes"] + 1))
            if part.stat().st_size != lock["sizeBytes"] or digest(part) != lock["sha256"]:
                raise DataError("Changed official development download")
            part.replace(path)
        finally:
            part.unlink(missing_ok=True)
    return verify_dev(directory)


def baseline(lines, year, pos):
    complete = [
        r
        for r in lines
        if r.year == year and r.position == pos and r.chances and (r.counts["InnOuts"] or 0) >= 900
    ]
    return {
        "errors": sum(r.counts["E"] for r in complete),
        "chances": sum(r.chances for r in complete),
        "players": len(complete),
    }


def effect(line, reference, floor=MIN_INNINGS, prior=PRIOR_CHANCES):
    if line is None or line.chances is None or line.counts["InnOuts"] is None:
        return "unknown", SCALE
    if not line.chances or line.counts["InnOuts"] < floor * 3:
        return "insufficient", SCALE
    if not reference["errors"] or not reference["chances"]:
        return "unknown", SCALE
    mu = Fraction(reference["errors"], reference["chances"])
    rate = (line.counts["E"] + prior * mu) / (line.chances + prior)
    scaled = rate / mu * SCALE
    # Exact nonnegative half-up rounding, independent of binary floating point.
    return "observed", (2 * scaled.numerator + scaled.denominator) // (2 * scaled.denominator)


def reliability(lines):
    lookup = {(r.player, r.year, r.position): r for r in lines}
    references = {(y, p): baseline(lines, y, p) for y in (2022, 2023, 2024) for p in POSITIONS}
    trials = []
    for floor in (100, 300, 600):
        for prior in (100, 300, 1000, 3000):
            scores = []
            for year in (2022, 2023):
                loss, neutral, n, used = 0, 0, 0, 0
                for target in lines:
                    if (
                        target.year != year + 1
                        or not target.chances
                        or (target.counts["InnOuts"] or 0) < 900
                    ):
                        continue
                    ref = references[year, target.position]
                    mu = ref["errors"] / ref["chances"]
                    status, relative = effect(
                        lookup.get((target.player, year, target.position)), ref, floor, prior
                    )
                    probability = max(1e-10, min(1 - 1e-10, relative / SCALE * mu))
                    errors, tc = target.counts["E"], target.chances
                    loss -= errors * math.log(probability) + (tc - errors) * math.log1p(
                        -probability
                    )
                    neutral -= errors * math.log(mu) + (tc - errors) * math.log1p(-mu)
                    n += tc
                    used += status == "observed"
                scores.append(
                    {
                        "from": year,
                        "to": year + 1,
                        "chances": n,
                        "used": used,
                        "logLossChangePerChance": (loss - neutral) / n,
                    }
                )
            trials.append({"minInnings": floor, "priorChances": prior, "scores": scores})
    return trials


def event_audit(directory, year, model):
    """Only clearly attributed batter ROE; advancing-only and compound errors unchanged."""
    counts, by_choice = Counter(), Counter()
    cells = {(c["outs"], c["baseMask"]): c for c in model["cells"] if c["event"] == "otherContact"}
    for row in retrosheet.zip_rows(directory, f"{year}plays.zip", f"{year}plays.csv", headers=True):
        if row["gametype"] != "regular" or row["pbp"] != "full" or int(row["inning"]) > 8:
            continue
        if row["pa"] != "1" or row["sh"] != "0" or row["sf"] != "0":
            continue
        counts["pa"] += 1
        errors = [i for i in range(1, 10) if int(row[f"e{i}"])]
        counts["errorPlays"] += bool(errors)
        counts["batterROE"] += row["roe"] == "1"
        counts["errorWithoutBatterROE"] += bool(errors) and row["roe"] != "1"
        if row["roe"] != "1" or contact_event(row) != "otherContact":
            continue
        outs, mask, _ = play_flags(row)
        transition, reason = supported_transition(row, "otherContact", outs, mask)
        if transition[2] != "error":
            counts["unsupportedROE"] += 1
            continue
        counts["supportedROE"] += 1
        if len(errors) != 1 or int(row[f"e{errors[0]}"]) != 1 or row["firstf"] != str(errors[0]):
            counts["ambiguousROE"] += 1
            continue
        if errors[0] == 1:
            counts["pitcherROE"] += 1
            continue
        hold = conservative("otherContact", outs, mask)
        cell = cells[outs, mask]
        out_index = next(
            (
                i
                for i, c in enumerate(cell["choices"])
                if tuple(c["destinations"]) == hold[0] and not c.get("reach")
            ),
            None,
        )
        index = next(
            (
                i
                for i, c in enumerate(cell["choices"])
                if tuple(c["destinations"]) == transition[0]
                and tuple(c["rbi"]) == transition[1]
                and c.get("reach") == "error"
            ),
            None,
        )
        if out_index is None or index is None:
            counts["noSupportedPair"] += 1
            continue
        counts["modifiableROE"] += 1
        counts[f"position{errors[0]}"] += 1
        by_choice[outs, mask, index, errors[0]] += 1
    return dict(counts), by_choice


def environment(model, source_id, audits):
    observations = Counter()
    for _, rows in audits:
        observations.update(rows)
    position_counts = Counter()
    for (_, _, _, position), n in observations.items():
        position_counts[position] += n
    supported = [p for p in range(2, 10) if position_counts[p] >= 50]
    cells = []
    for cell in model["cells"]:
        if cell["event"] != "otherContact":
            continue
        outs, mask = cell["outs"], cell["baseMask"]
        hold = conservative("otherContact", outs, mask)
        ordinary = next(
            (
                i
                for i, c in enumerate(cell["choices"])
                if tuple(c["destinations"]) == hold[0] and not c.get("reach")
            ),
            None,
        )
        parts = [
            {"choiceIndex": i, "position": p, "weight": n * SCALE // cell["observations"]}
            for (o, b, i, p), n in sorted(observations.items())
            if o == outs and b == mask and p in supported
        ]
        cells.append(
            {"outs": outs, "baseMask": mask, "ordinaryIndex": ordinary, "components": parts}
        )
    body = {
        "schemaVersion": "1.0.0",
        "modelVersion": VERSION,
        "year": 2024,
        "sourceId": source_id,
        "transitionModelId": model["id"],
        "retrosheetLockSha256": lock_digest(retrosheet.source_lock()),
        "supportedPositions": [POSITIONS[p - 2] for p in supported],
        "minimumAttributedEvents": 50,
        "cells": cells,
    }
    return {"id": identity(body, "defense-model"), **body}


def write_supplement(output, supplement):
    data = canonical_bytes(supplement) + b"\n"
    if output.exists() and output.read_bytes() != data:
        raise DataError("Refusing to overwrite immutable defensive supplement")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)


def prepare(source, retro, dev, publication, output, report):
    provenance = verify_source(source)
    retrosheet.verify(retro)
    dev_info = verify_dev(dev)
    players, manifest = load_publication(publication, ROOT / "infra/d1/migrations")
    if manifest["datasetId"] != DATASET_ID or manifest["metadata"]["source"] != provenance:
        raise DataError("Defense requires unchanged 2024 pilot")
    fixture = ROOT / "crates/baseball-sim/tests/fixtures/season-modern-2024.json"
    if digest(fixture) != FIXTURE_SHA:
        raise DataError("Changed M4 fixture")
    model = json.loads(fixture.read_text("utf-8"))["config"]["contextualModel"]
    lines = aggregate_fielding(
        {t: list(read_table(source, t)) for t in ("Fielding.csv", "FieldingOFsplit.csv")}
    )
    lookup = {(r.player, r.year, r.position): r for r in lines}
    training = [event_audit(retro, y, model) for y in (2022, 2023)]
    development, _ = event_audit(dev, 2024, model)
    env = environment(model, manifest["metadata"]["sourceId"], training)
    references = {p: baseline(lines, 2024, p) for p in POSITIONS}
    profiles = []
    for player in players:
        for pos in POSITIONS:
            if (player["appearances"].get(pos) or 0) < 10:
                continue
            line = lookup.get((player["id"].removeprefix("lahman:"), 2024, pos))
            status, relative = effect(line, references[pos])
            if pos not in env["supportedPositions"] and status == "observed":
                status, relative = "modelNeutral", SCALE
            body = {
                "schemaVersion": "1.0.0",
                "modelId": env["id"],
                "sourceId": env["sourceId"],
                "playerId": player["id"],
                "battingProfileId": player["profile"]["id"],
                "year": 2024,
                "position": pos,
                "status": status,
                "errorRatio": relative,
                "games": line.counts["G"] if line else None,
                "innOuts": line.counts["InnOuts"] if line else None,
                "chances": line.chances if line else None,
                "errors": line.counts["E"] if line else None,
            }
            profiles.append({"id": identity(body, "defense"), **body})
    body = {
        "schemaVersion": "1.0.0",
        "modelVersion": VERSION,
        "datasetId": DATASET_ID,
        "source": provenance,
        "year": 2024,
        "model": env,
        "references": references,
        "policy": {
            "minInnings": MIN_INNINGS,
            "priorChances": PRIOR_CHANCES,
            "rounding": "half-up-millionths",
            "referenceMinInnings": 300,
        },
        "attribution": retrosheet.RETROSHEET_NOTICE
        + " SABR Lahman 2025, Sean Lahman/Bryan Walko and contributors; CC BY-SA 3.0.",
        "profiles": profiles,
    }
    supplement = {"id": identity(body, "defense-supplement"), **body}
    write_supplement(output, supplement)
    result = {
        "schemaVersion": "1.0.0",
        "supplementId": supplement["id"],
        "supplementSha256": digest(output),
        "developmentSource": dev_info,
        "training": [a for a, _ in training],
        "development": development,
        "reliability": reliability(lines),
        "references": references,
        "coverage": {
            p: dict(Counter(r["status"] for r in profiles if r["position"] == p)) for p in POSITIONS
        },
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_bytes(canonical_bytes(result) + b"\n")
    return supplement, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fetch-dev", "prepare"))
    parser.add_argument("--source-dir", type=Path, default=ROOT / "data/raw/lahman-2025")
    parser.add_argument("--retrosheet-dir", type=Path, default=ROOT / "data/raw/retrosheet-m4")
    parser.add_argument("--dev-dir", type=Path, default=ROOT / "data/raw/retrosheet-defense-2024")
    parser.add_argument("--publication-dir", type=Path, default=ROOT / "data/processed/d1-2024")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/publications/defense-2024-v1.json"
    )
    parser.add_argument(
        "--report", type=Path, default=ROOT / "data/validation/defense-v1-data.json"
    )
    args = parser.parse_args()
    if args.command == "fetch-dev":
        print(fetch_dev(args.dev_dir))
    else:
        supplement, result = prepare(
            args.source_dir,
            args.retrosheet_dir,
            args.dev_dir,
            args.publication_dir,
            args.output,
            args.report,
        )
        print(json.dumps({"id": supplement["id"], "coverage": result["coverage"]}, indent=2))


if __name__ == "__main__":
    main()
