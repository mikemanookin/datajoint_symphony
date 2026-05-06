# Testing Guide

Running the test suite, understanding what each layer asserts, and
extending it. Spec: [`spec/05_testing.md`](../spec/05_testing.md).

## TL;DR

```bash
# 1. Bring MySQL up.
cd config && docker compose up -d && cd ..
./scripts/wait_for_mysql.sh

# 2. Run.
python -m pytest                    # full suite
python -m pytest -k "not integration"   # unit-only (no DB needed)
```

## Layout

```
tests/
  conftest.py                      # fixtures
  fixtures/
    sample_dj.json                 # one-experiment DJ JSON
    sample_tags.json               # matching tags sidecar
  test_config.py                   # YAML loading, env-var precedence
  test_timestamps.py               # .NET ticks ↔ datetime
  test_schema.py                   # schema declarations valid (no DB)
  test_ingest_unit.py              # tuple builders (no DB)
  test_ingest_integration.py       # full ingest into MySQL
  test_query.py                    # query helpers
  test_invariants.py               # the five DJ JSON invariants
```

## Tiers

**Unit tier (no DB).** Runs anywhere with just `pip install pytest pyyaml
datajoint`:

- `test_config.py`, `test_timestamps.py`, `test_schema.py`,
  `test_ingest_unit.py`.

**Integration tier (Docker MySQL).** Requires the fixture in
`config/docker-compose.yaml` to be running:

- `test_ingest_integration.py`, `test_query.py`, `test_invariants.py`.

Both tiers run when MySQL is available. The integration tier is
auto-skipped (`pytest.skip("MySQL unavailable")`) if it isn't, so a
"unit-only" environment still produces a green run.

## Common operations

```bash
# Run one file
python -m pytest tests/test_schema.py

# Verbose
python -m pytest -v

# Stop on first failure
python -m pytest -x

# Show stdout (helpful when debugging fixtures)
python -m pytest -s
```

## Adding tests

- Pure-mapping tests go in `test_ingest_unit.py`. They take a JSON
  fixture (or a literal Python dict) and call one of the
  `build_*_tuple` functions.
- DB-touching tests use the `db` fixture. Each test gets a fresh schema
  on a unique name; the fixture tears it down at teardown.
- New ingestion behaviors should add a row-count assertion in
  `test_ingest_integration.py` and a contract assertion in
  `test_invariants.py` if the change affects round-trip fidelity.

## CI

Suggested CI snippet (GitHub Actions):

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
  with: { python-version: '3.11' }
- run: pip install -e '.[dev]'
- run: docker compose -f config/docker-compose.yaml up -d
- run: ./scripts/wait_for_mysql.sh
- run: python -m pytest
```
