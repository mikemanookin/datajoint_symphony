"""01_connect.py — verify your config, connect to the database.

Walks through the connection lifecycle:

1. Load config from YAML / env vars.
2. Open the DataJoint connection.
3. Print the table list and row counts.

Usage::

    python scripts/01_connect.py

If you don't have a database running, ``cd config && docker compose up -d``
first. See docs/installation.md.
"""
from symphony_dj import connect, load_config


def main() -> int:
    cfg = load_config()
    print("Loaded config from:", cfg.source_path or "(defaults)")
    print(f"  database: {cfg.database.user}@{cfg.database.host}:{cfg.database.port}")
    print(f"  schema:   {cfg.schema_name}")
    print(f"  paths.json_root: {cfg.paths.json_root}")
    print()

    with connect(cfg) as db:
        print(f"Connected: {db}")
        print()
        print("Tables (with row counts):")
        for name in (
            "Experiment Animal Preparation Cell EpochGroup EpochBlock "
            "Epoch Response Stimulus Background Protocol Tag"
        ).split():
            cls = getattr(db, name)
            print(f"  {name:<14} {len(cls):>6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
