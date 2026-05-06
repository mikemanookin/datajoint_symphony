"""02_ingest_json.py — ingest *_dj.json files into the database.

Examples::

    # Ingest one file:
    python scripts/02_ingest_json.py /Volumes/data/data/json/20260410H_dj.json

    # Ingest a whole directory of *_dj.json files:
    python scripts/02_ingest_json.py /Volumes/data/data/json/

Every entity from the JSON is keyed by its upstream UUID, so re-running
this against the same file is a no-op. See spec/02_ingestion.md.
"""
import argparse
import sys
from pathlib import Path

from symphony_dj import connect


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="JSON file or directory")
    parser.add_argument("--tags", help="Optional tags sidecar JSON file")
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Fail on duplicate primary keys (default: skip silently)",
    )
    args = parser.parse_args()

    path = Path(args.path).expanduser()
    if not path.exists():
        sys.stderr.write(f"Path does not exist: {path}\n")
        return 1

    with connect() as db:
        if path.is_dir():
            report = db.ingest_directory(
                path, skip_existing=not args.no_skip_existing
            )
        else:
            report = db.ingest_json(
                path,
                tags_path=args.tags,
                skip_existing=not args.no_skip_existing,
            )
        print(report)
        return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
