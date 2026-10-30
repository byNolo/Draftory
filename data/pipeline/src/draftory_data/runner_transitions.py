"""Opt-in M9B.1 joint outcomes; immutable v1 fitter and batting weights are untouched."""

import argparse
import json
import re
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

from . import retrosheet
from .calibration import write
from .defense import verify_dev
from .defense_research import contact_event, play_flags
from .simulation import identity
from .source import DataError, canonical_bytes, lock_digest
from .transitions import EVENTS, MIN_CELL_OBSERVATIONS, conservative, supported_transition
from .valuation import ROOT

MODEL = "retrosheet-runner-transitions-v1"
RULES = "runner-outs-nine-inning-v1"
POLICY = "retrosheet-runner-outs-v1"


def classify(row, event, outs, mask):
    """Only promote source-reconciled cases. No order inferred from semicolon order."""
    legacy, reason = supported_transition(row, event, outs, mask)
    fallback = (*legacy, None)
    if reason in (
        "ground-double-play",
        "observed-error",
        "observed-fieldersChoice",
        "observed-safe-transition",
    ):
        return fallback, "legacy:" + reason
    if "?" in row["event"] or "#" in row["event"]:
        return fallback, "proxy:uncertain-source"
    if "/AP" in row["event"]:
        return fallback, "proxy:appeal"
    if any(
        int(row[k])
        for k in (
            "sh",
            "sf",
            "wp",
            "pb",
            "bk",
            "sb2",
            "sb3",
            "sbh",
            "cs2",
            "cs3",
            "csh",
            "pko1",
            "pko2",
            "pko3",
            "oa",
            "tp",
            "othdp",
        )
    ):
        return fallback, "proxy:compound-or-other-dp"
    before = [row["batter"], *(row[f"br{i}_pre"] for i in range(1, 4))]
    if not before[0] or len([x for x in before if x]) != len({x for x in before if x}):
        return fallback, "proxy:identity"
    delta = int(row["outs_post"]) - outs
    terminal = outs + delta == 3
    if delta not in (0, 1):
        return fallback, "proxy:multiple-or-invalid-outs"
    main, _, advances = row["event"].partition(".")
    explicit = {}
    for token in advances.split(";") if advances else []:
        match = re.fullmatch(r"([B123])([-X])([123H])((?:\([^()]*\))*)", token)
        if not match:
            return fallback, "proxy:advance-syntax"
        origin = 0 if match[1] == "B" else int(match[1])
        if origin in explicit or not before[origin]:
            return fallback, "proxy:advance-identity"
        # An X with an error can mean safe; retain the old proxy, don't guess.
        if match[2] == "X" and ("E" in match[4] or "AP" in match[4]):
            return fallback, "proxy:error-or-appeal-out"
        explicit[origin] = (match[2], 4 if match[3] == "H" else int(match[3]))
    hit = 1 if event == "single" else 2 if event == "double" else 0
    force = re.findall(r"\(([123])\)", main.split("/")[0])
    if not hit:
        # Narrow force-choice class: one explicitly identified forced runner, no scores.
        if delta != 1 or "/FO" not in main or len(force) != 1 or int(row["roe"]):
            return fallback, "proxy:contact-out-or-timing"
        forced = int(force[0])
        if mask & ((1 << forced) - 1) != (1 << forced) - 1:
            return fallback, "proxy:unproven-force"
    else:
        forced = None
    d, kinds, rbi, out_bases = [5] * 4, ["none"] * 4, [False] * 4, [0] * 4
    lob = {row[f"lob_id{i}"] for i in range(1, 4)} - {""}
    post = [row[f"br{i}_post"] for i in range(1, 4)]
    for origin, player in enumerate(before):
        if not player:
            continue
        score_key = "run_b" if origin == 0 else f"run{origin}"
        rbi_key = "rbi_b" if origin == 0 else f"rbi{origin}"
        scored = row[score_key] == player
        if row[score_key] and not scored:
            return fallback, "proxy:scoring-identity"
        raw = explicit.get(origin)
        out_key = "brout_b" if origin == 0 else f"brout{origin}"
        if origin == forced:
            dest, kind = 0, "force"
            out_bases[origin] = origin + 1
        elif raw and raw[0] == "X":
            if row[out_key] in ("", "0") or raw[1] <= (hit if origin == 0 else origin):
                return fallback, "proxy:unproven-running-out"
            dest, kind = 0, "tag"
            out_bases[origin] = raw[1]
        elif scored:
            dest, kind = 4, "none"
        elif not terminal and player in post:
            dest, kind = post.index(player) + 1, "none"
        elif terminal and player in lob:
            # Explicit advance, implied hit base, or unchanged original base; LOB proves survival.
            dest = raw[1] if raw and raw[0] == "-" else hit if origin == 0 else origin
            kind = "none"
        else:
            return fallback, "proxy:unresolved-destination"
        if raw and raw[0] == "-" and raw[1] != dest:
            return fallback, "proxy:raw-parsed-disagreement"
        d[origin], kinds[origin] = dest, kind
        if row[rbi_key] not in ("0", "1"):
            return fallback, "proxy:unknown-rbi"
        rbi[origin] = row[rbi_key] == "1"
        if rbi[origin] and dest != 4:
            return fallback, "proxy:rbi"
    if sum(x == 0 for x in d) != delta or set(post) - {""} - set(before):
        return fallback, "proxy:out-or-identity-reconciliation"
    if terminal and lob != {p for p, dest in zip(before, d, strict=True) if p and 1 <= dest <= 3}:
        return fallback, "proxy:lob-reconciliation"
    survivors = [x for x in d if x not in (0, 5)]
    if (
        survivors != sorted(survivors)
        or len([x for x in survivors if x < 4]) != len({x for x in survivors if x < 4})
        or any(0 < dest < origin for origin, dest in enumerate(d) if dest != 5)
        or (hit and d[0] not in (0, *range(hit, 5)))
    ):
        return fallback, "proxy:collision-passing-or-backwards"
    scores = 4 in d
    # Source credited runs establish timing only for a single non-force third out.
    if scores and delta and not (terminal and kinds.count("tag") == 1):
        return fallback, "proxy:unresolved-run-out-order"
    if not hit and scores:
        return fallback, "proxy:force-scoring"
    if scores and delta and any(dest == 4 for dest in d[: kinds.index("tag") + 1]):
        return fallback, "proxy:passing-at-timing-out"
    play = {"outKinds": kinds, "outBases": out_bases, "runsBeforeOuts": bool(scores and delta)}
    label = (
        "supported:force-choice"
        if not hit
        else (
            "supported:timing-third-out"
            if scores and delta
            else "supported:hit-running-out"
            if delta
            else "supported:extra-batter-advance"
        )
    )
    return (
        tuple(d),
        tuple(rbi),
        "fieldersChoice" if not hit else "none",
        canonical_bytes(play).decode(),
    ), label


def rows(directory, year):
    for row in retrosheet.zip_rows(directory, f"{year}plays.zip", f"{year}plays.csv", headers=True):
        if (
            row["gametype"] == "regular"
            and row["pbp"] == "full"
            and int(row["inning"]) <= 8
            and row["pa"] == "1"
            and row["sh"] == row["sf"] == "0"
        ):
            event = contact_event(row)
            if event:
                yield row, event


def collect(directory, year):
    counts, reasons, old_reasons = defaultdict(Counter), Counter(), Counter()
    cross, targets, direct = Counter(), Counter(), Counter()
    for row, event in rows(directory, year):
        outs, mask, _ = play_flags(row)
        outcome, reason = classify(row, event, outs, mask)
        counts[event, outs, mask][outcome] += 1
        reasons[reason] += 1
        _, old = supported_transition(row, event, outs, mask)
        old_reasons[old] += 1
        cross[f"{event}:{reason}"] += 1
        if reason.startswith("supported:"):
            previous, _ = supported_transition(row, event, outs, mask)
            direct["outsDelta"] += outcome[0].count(0) - previous[0].count(0)
            direct["runsDelta"] += outcome[0].count(4) - previous[0].count(4)
            direct["rbiDelta"] += sum(outcome[1]) - sum(previous[1])
            play = json.loads(outcome[3])
            for kind, base in zip(play["outKinds"], play["outBases"], strict=True):
                if kind != "none":
                    targets[f"{event}:{kind}:base{base}"] += 1
    return counts, {
        "year": year,
        "denominator": sum(reasons.values()),
        "classifications": dict(sorted(reasons.items())),
        "legacyClassifications": dict(sorted(old_reasons.items())),
        "eventClassifications": dict(sorted(cross.items())),
        "outTargets": dict(sorted(targets.items())),
        "directChangeOnObservedStates": dict(direct),
    }


def prepare(output):
    source = retrosheet.verify(ROOT / "data/raw/retrosheet-m4")
    dev = verify_dev(ROOT / "data/raw/retrosheet-defense-2024")
    combined, audits = defaultdict(Counter), []
    for year in (2022, 2023, 2024):
        counts, audit = collect(
            ROOT
            / ("data/raw/retrosheet-defense-2024" if year == 2024 else "data/raw/retrosheet-m4"),
            year,
        )
        audits.append(audit)
        if year != 2024:
            for key, values in counts.items():
                combined[key].update(values)
    cells, sparse = [], []
    for event in EVENTS:
        for outs in range(3):
            for mask in range(8):
                counter = combined[event, outs, mask]
                n = counter.total()
                fallback = n < MIN_CELL_OBSERVATIONS
                if fallback:
                    sparse.append({"event": event, "outs": outs, "baseMask": mask, "n": n})
                    counter = Counter({(*conservative(event, outs, mask), None): 1})
                # None sorts separately without comparing str and None.
                items = sorted(counter.items(), key=lambda item: canonical_bytes(item[0]))
                scaled = [Fraction(n * 1_000_000, counter.total()) for _, n in items]
                weights = [x.numerator // x.denominator for x in scaled]
                order = sorted(range(len(items)), key=lambda i: (-(scaled[i] - weights[i]), i))
                for i in order[: 1_000_000 - sum(weights)]:
                    weights[i] += 1
                choices = [
                    {
                        "destinations": d,
                        "rbi": r,
                        "weight": w,
                        **({"reach": reach} if reach != "none" else {}),
                        **({"runnerPlay": json.loads(play)} if play else {}),
                    }
                    for ((d, r, reach, play), _), w in zip(items, weights, strict=True)
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
        "modelVersion": MODEL,
        "sourceId": "retrosheet:" + lock_digest(retrosheet.source_lock()),
        "cells": cells,
    }
    model = {"id": identity(body, "runner-transitions"), **body}
    output.mkdir(parents=True, exist_ok=True)
    path = output / "transitions.json"
    encoded = canonical_bytes(model) + b"\n"
    if path.exists() and path.read_bytes() != encoded:
        raise DataError("Refusing to overwrite different transition artifact")
    path.write_bytes(encoded)
    write(
        output / "source-audit.json",
        {
            "source": source,
            "developmentArchive": dev,
            "trainingYears": [2022, 2023],
            "developmentYears": [2024],
            "audits": audits,
            "minimumCellObservations": MIN_CELL_OBSERVATIONS,
            "sparseCells": sparse,
            "modelId": model["id"],
            "maxChoices": max(len(c["choices"]) for c in cells),
        },
    )
    return model


def upgrade(value, model):
    if (
        "defense" in value["config"]
        or value["schemaVersion"] != "1.0.0"
        or value["gameSchemaVersion"] != "1.2.0"
        or value["rulesVersion"] != "contextual-nine-inning-v1"
        or value["config"]["advancementPolicy"] != "retrosheet-contextual-v1"
    ):
        raise DataError("Runner mode requires neutral v1 contextual input; defense is incompatible")
    return {
        **value,
        "schemaVersion": "1.2.0",
        "gameSchemaVersion": "1.4.0",
        "rulesVersion": RULES,
        "config": {**value["config"], "advancementPolicy": POLICY, "contextualModel": model},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/processed/m9b1/verified")
    args = parser.parse_args()
    model = prepare(args.output_dir)
    fixture = json.loads(
        (ROOT / "crates/baseball-sim/tests/fixtures/season-modern-2024.json").read_text("utf-8")
    )
    write(args.output_dir / "season.json", upgrade(fixture, model))
    print(model["id"])


if __name__ == "__main__":
    main()
