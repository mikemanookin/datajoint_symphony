# `datajoint_symphony` — Documentation

User-facing docs for the package. Specs and design rationale live in
[`../spec/`](../spec/); this directory is the how-to surface.

| Doc | What it covers |
|---|---|
| [`installation.md`](installation.md) | Python, MySQL (Docker), package install |
| [`configuration.md`](configuration.md) | `datajoint_config.yaml`, env vars, secrets |
| [`schema_reference.md`](schema_reference.md) | Every table, every column |
| [`ingestion_guide.md`](ingestion_guide.md) | Running an ingest, idempotency, troubleshooting |
| [`query_guide.md`](query_guide.md) | Querying from Python and Jupyter |
| [`testing_guide.md`](testing_guide.md) | Running pytest, the Docker fixture, CI |
| [`migration_v2.md`](migration_v2.md) | What changed from the legacy `old/` codebase |

## 30-second tour

```bash
# 1. Bring up MySQL.
cd config && docker compose up -d && cd ..

# 2. Connect & create the schema.
python -m symphony_dj init

# 3. Ingest a JSON.
python -m symphony_dj ingest /path/to/20260410H_dj.json

# 4. Query in Python.
python -c 'from symphony_dj import connect; db = connect(); print(db.Experiment.fetch())'
```

For Jupyter, open
[`scripts/04_query_jupyter.ipynb`](../scripts/04_query_jupyter.ipynb).
