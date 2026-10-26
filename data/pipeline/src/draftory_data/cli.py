"""Offline CLI: acquisition, inspection, normalized facts and descriptive profiles."""

import argparse
import sys
from pathlib import Path
from urllib.error import URLError

from .inspection import inspect_source, write_inspection
from .normalize import Dataset
from .profiles import ProfileRequest, generate_profile
from .source import DataError, canonical_bytes, fetch, verify_source


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="draftory-data")
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("fetch", "verify", "inspect", "normalize", "profile"):
        command = commands.add_parser(name)
        command.add_argument("--source-dir", type=Path, required=True)
        if name in ("inspect", "normalize"):
            command.add_argument("--output-dir", type=Path, required=True)
        if name == "profile":
            command.add_argument("--player", required=True)
            command.add_argument("--leagues", nargs="+", required=True)
            command.add_argument(
                "--method",
                choices=["aggregate", "season_rate_mean", "season_rate_median"],
                default="aggregate",
            )
            command.add_argument("--start-year", type=int)
            command.add_argument("--end-year", type=int)
            command.add_argument("--team")
            command.add_argument("--franchise")
            command.add_argument("--min-season-pa", type=int, default=1)
            command.add_argument("--min-seasons", type=int, default=1)
            command.add_argument("--output", type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "fetch":
            output = fetch(args.source_dir)
        elif args.command == "verify":
            output = verify_source(args.source_dir)
        else:
            dataset = Dataset.load(args.source_dir)
            if args.command == "inspect":
                output = inspect_source(args.source_dir, dataset)
                write_inspection(output, args.output_dir)
                output = {
                    "source": output["source"],
                    "tables": {name: table["rows"] for name, table in output["tables"].items()},
                    "report": str(args.output_dir / "data-quality-report.md"),
                }
            elif args.command == "normalize":
                output = dataset.write(args.output_dir)
            else:
                request = ProfileRequest(
                    args.player,
                    args.method,
                    tuple(args.leagues),
                    args.start_year,
                    args.end_year,
                    args.team,
                    args.franchise,
                    args.min_season_pa,
                    args.min_seasons,
                )
                output = generate_profile(dataset, request)
                if args.output:
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    args.output.write_bytes(canonical_bytes(output) + b"\n")
        print(canonical_bytes(output).decode("utf-8"))
        return 3 if output.get("status") == "insufficient_data" else 0
    except (DataError, OSError, URLError) as error:
        print(f"draftory-data: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
