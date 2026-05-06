# `datajoint_symphony`

DataJoint 2.0 ingestion + query for Symphony 3 metadata.

```
Symphony H5  ──parse_data.py──▶  *_dj.json  ──symphony_dj──▶  DataJoint MySQL
```

This repo is **spec-driven**. Specs and ADRs in [`spec/`](spec/) are the
source of truth; code in [`src/python/symphony_dj/`](src/python/symphony_dj/)
implements them; [`tests/`](tests/) gates them.

## 30-second tour

```bash
cd config && docker compose up -d && cd ..    # 1. MySQL
python -m symphony_dj init                     # 2. create the schema
python -m symphony_dj ingest /path/to/json/    # 3. load some data
python scripts/03_query_python.py              # 4. query
```

## Where things live

| Path | What |
|---|---|
| [`spec/`](spec/) | Specs and ADRs — the design, source of truth |
| [`src/python/symphony_dj/`](src/python/symphony_dj/) | The Python package |
| [`config/datajoint_config.yaml`](config/datajoint_config.yaml) | Example config (and Docker default) |
| [`config/docker-compose.yaml`](config/docker-compose.yaml) | MySQL fixture for dev + tests |
| [`scripts/`](scripts/) | Connect / ingest / query examples (Python + Jupyter) |
| [`docs/`](docs/) | User-facing docs (installation, configuration, etc.) |
| [`tests/`](tests/) | pytest suite (unit + integration) |
| [`old/`](old/) | Pre-rewrite legacy code (read-only reference) |

## Read me first

1. [`spec/README.md`](spec/README.md) — spec index and pipeline overview
2. [`docs/installation.md`](docs/installation.md) — get running in 5 minutes
3. [`docs/migration_v2.md`](docs/migration_v2.md) — what changed from `old/`

## Configuration

Everything environment-specific lives in
[`config/datajoint_config.yaml`](config/datajoint_config.yaml) (or
`~/.datajoint_config.yaml`, or the env vars `DJ_HOST`, `DJ_USER`,
`DJ_PASSWORD`, ...). Full details in
[`docs/configuration.md`](docs/configuration.md).
