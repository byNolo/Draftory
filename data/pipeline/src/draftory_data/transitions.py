"""Fit a small explicit transition model using training plays, never holdout plays."""

from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

from .retrosheet import source_lock, verify, zip_rows
from .simulation import identity
from .source import DataError, lock_digest

EVENTS = ("single", "double", "otherContact")
MIN_CELL_OBSERVATIONS = 50


def conservative(event: str, outs: int, mask: int):
    d = [0 if event == "otherContact" else (1 if event == "single" else 2), 5, 5, 5]
    for base in range(1, 4):
        if not mask & (1 << (base - 1)):
            continue
        if event == "otherContact":
            d[base] = base
        elif event == "single":
            d[base] = 2 if base == 1 else (3 if base == 2 and outs < 2 else 4)
        else:
            d[base] = 3 if base == 1 and outs < 2 else 4
    return tuple(d), tuple(x == 4 for x in d), "none"


def destination(row: dict, identity_: str, score_field: str) -> int:
    if row[score_field] == identity_:
        return 4
    for base in range(1, 4):
        if row[f"br{base}_post"] == identity_:
            return base
    return 0


def supported_transition(row: dict, event: str, outs: int, mask: int):
    fallback = conservative(event, outs, mask)
    delta = int(row["outs_post"]) - outs
    batter_dest = destination(row, row["batter"], "run_b")
    if any(int(row[k]) for k in ("wp", "pb", "bk", "sb2", "sb3", "sbh", "cs2", "cs3", "csh", "oa")):
        return fallback, "compound-event-proxy"
    reach = "none"
    if event == "otherContact":
        if int(row["gdp"]) and mask & 1 and outs < 2 and delta == 2:
            d = list(fallback[0])
            d[1] = 0
            return (tuple(d), (False,) * 4, "none"), "ground-double-play"
        if int(row["roe"]) and delta == 0:
            reach = "error"
        elif (
            1 <= batter_dest <= 3
            and outs + delta < 3
            and ((int(row["fc"]) and delta in (0, 1)) or (int(row["othout"]) and delta == 1))
        ):
            reach = "fieldersChoice"
        elif not int(row["othout"]) or delta != 1 or outs == 2:
            return fallback, "third-out-or-unsupported-contact-proxy"
    elif delta != 0:
        return fallback, "running-out-on-hit-proxy"
    d = [0 if event == "otherContact" else (1 if event == "single" else 2), 5, 5, 5]
    if reach != "none":
        if not 1 <= batter_dest <= 3:
            return fallback, "unsupported-contact-reach-proxy"
        d[0] = batter_dest
    if batter_dest != d[0]:
        return fallback, "batter-extra-advance-proxy"
    rbi = [False] * 4
    for base in range(1, 4):
        runner = row[f"br{base}_pre"]
        if runner:
            d[base] = destination(row, runner, f"run{base}")
            rbi[base] = bool(int(row[f"rbi{base}"]))
            if (d[base] == 0 and reach != "fieldersChoice") or (rbi[base] and d[base] != 4):
                return fallback, "unsupported-runner-out-proxy"
    # Preserve runner order; no collisions or passing.
    survivors = [x for x in d if x not in (0, 5)]
    bases = [x for x in survivors if x < 4]
    if survivors != sorted(survivors) or len(set(bases)) != len(bases):
        return fallback, "unsupported-advance-proxy"
    if sum(x == 0 for x in d) != delta:
        return fallback, "unsupported-out-count-proxy"
    return (tuple(d), tuple(rbi), reach), "observed-" + (
        reach if reach != "none" else "safe-transition"
    )


def fit_model(directory: Path) -> tuple[dict, dict]:
    provenance = verify(directory)
    counts = defaultdict(Counter)
    reasons = Counter()
    for year in source_lock()["trainingYears"]:
        for row in zip_rows(directory, f"{year}plays.zip", f"{year}plays.csv", headers=True):
            if row["gametype"] != "regular" or row["pbp"] != "full" or int(row["inning"]) > 8:
                continue
            if row["pa"] != "1" or row["sh"] != "0" or row["sf"] != "0":
                continue
            event = "single" if row["single"] == "1" else "double" if row["double"] == "1" else None
            if (
                event is None
                and row["ab"] == "1"
                and all(row[k] == "0" for k in ("single", "double", "triple", "hr", "k"))
            ):
                event = "otherContact"
            if event is None:
                continue
            outs = int(row["outs_pre"])
            mask = sum(1 << (i - 1) for i in range(1, 4) if row[f"br{i}_pre"])
            transition, reason = supported_transition(row, event, outs, mask)
            counts[event, outs, mask][transition] += 1
            reasons[reason] += 1
    cells = []
    fallback_cells = []
    for event in EVENTS:
        for outs in range(3):
            for mask in range(8):
                observed = counts[event, outs, mask]
                n = observed.total()
                fallback = n < MIN_CELL_OBSERVATIONS
                if fallback:
                    observed = Counter({conservative(event, outs, mask): 1})
                    fallback_cells.append(
                        {"event": event, "outs": outs, "baseMask": mask, "observations": n}
                    )
                total = observed.total()
                items = sorted(observed.items())
                scaled = [Fraction(v * 1_000_000, total) for _, v in items]
                weights = [v.numerator // v.denominator for v in scaled]
                order = sorted(range(len(items)), key=lambda i: (-(scaled[i] - weights[i]), i))
                for i in order[: 1_000_000 - sum(weights)]:
                    weights[i] += 1
                choices = [
                    {
                        "destinations": d,
                        "rbi": r,
                        "weight": w,
                        **({"reach": reach} if reach != "none" else {}),
                    }
                    for ((d, r, reach), _), w in zip(items, weights, strict=True)
                    if w
                ]
                cells.append(
                    {
                        "event": event,
                        "outs": outs,
                        "baseMask": mask,
                        "observations": n,
                        "fallback": fallback,
                        "choices": choices,
                    }
                )
    body = {
        "modelVersion": "retrosheet-contact-transitions-v1",
        "sourceId": "retrosheet:" + lock_digest(source_lock()),
        "cells": cells,
    }
    model = {"id": identity(body, "transitions"), **body}
    if not cells or any(sum(c["weight"] for c in cell["choices"]) != 1_000_000 for cell in cells):
        raise DataError("Invalid transition probability mass")
    return model, {
        "source": provenance,
        "trainingYears": source_lock()["trainingYears"],
        "holdoutYears": source_lock()["holdoutYears"],
        "minimumCellObservations": MIN_CELL_OBSERVATIONS,
        "classificationCounts": dict(sorted(reasons.items())),
        "fallbackCells": fallback_cells,
    }
