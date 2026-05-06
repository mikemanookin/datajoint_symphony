"""Command-line interface for ``symphony_dj``.

Run with ``python -m symphony_dj``. Subcommands:

    init       Create the schema if missing.
    ingest     Ingest a JSON file or directory.
    drop       Drop the schema (DESTRUCTIVE).
    diagram    Print the table list (no GraphViz dependency).
    config     Print the resolved config (with redacted password).
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from . import connect, load_config


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="symphony_dj")
    p.add_argument(
        "--config",
        help="Path to datajoint_config.yaml (overrides default search)",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Connect and create the schema if missing")

    p_ingest = sub.add_parser("ingest", help="Ingest a JSON file or directory")
    p_ingest.add_argument("path", help="Path to a *_dj.json file or a directory")
    p_ingest.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Fail (instead of skipping) on duplicate primary keys",
    )

    sub.add_parser("drop", help="Drop the schema (DESTRUCTIVE)")
    sub.add_parser("diagram", help="Print the schema table list")
    sub.add_parser("config", help="Print the resolved config (password redacted)")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    cfg = load_config(args.config)

    if args.command == "config":
        d = cfg.database
        print(f"Database: {d.user}@{d.host}:{d.port} (password={'*' * len(d.password) if d.password else '(empty)'})")
        print(f"Schema:   {cfg.schema_name}")
        print(f"Source:   {cfg.source_path or '(defaults)'}")
        return 0

    if args.command == "diagram":
        with connect(cfg) as db:
            for name in sorted(db._tables):  # noqa: SLF001
                print(name)
        return 0

    if args.command == "init":
        with connect(cfg) as db:
            print(f"Connected: {db}")
            print(f"Tables: {len(db._tables)}")  # noqa: SLF001
        return 0

    if args.command == "drop":
        with connect(cfg) as db:
            db.drop()
        return 0

    if args.command == "ingest":
        with connect(cfg) as db:
            path = Path(args.path).expanduser()
            skip = not args.no_skip_existing
            if path.is_dir():
                report = db.ingest_directory(path, skip_existing=skip)
            else:
                report = db.ingest_json(path, skip_existing=skip)
            print(report)
            return 1 if report.errors else 0

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
