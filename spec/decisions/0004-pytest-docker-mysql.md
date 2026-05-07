# ADR 0004 — pytest with a Docker MySQL fixture

**Status:** Accepted
**Date:** 2026-05-06

## Context

DataJoint always talks to a real SQL server — there's no in-memory
backend. A test that exercises ingestion or query needs a live MySQL.
The legacy code had no automated tests, so this question never came up.

Three test models were on the table:

1. **Mock the DataJoint layer.** Replace `dj.Manual` subclasses with
   `Mock()` in tests. Fast but worthless: the bugs we actually hit
   (FK violations, JSON-encoding mismatches, varchar truncation) only
   show up against real MySQL.
2. **Hosted test DB.** Reuse the lab's MySQL. Pollutes a real DB,
   contention with humans using it, no clean state between tests.
3. **Docker MySQL fixture.** A short-lived MySQL container managed by
   `docker compose`. Real DataJoint behavior, isolated state, cleaned
   up between runs.

## Decision

Use `pytest` with a Docker Compose MySQL service. Tests that need the
DB depend on a `db` fixture that:

1. At session start, checks `dj.conn().is_connected` against the
   configured host. If unreachable, marks all dependent tests as
   `pytest.skip("MySQL unavailable")`.
2. At each test, declares a fresh `dj.Schema(test_schema_name)` and
   tears it down (`schema.drop_quick()`) at teardown.

Unit tests that don't touch the DB live in their own module
(`test_ingest_unit.py`, `test_config.py`, `test_timestamps.py`,
`test_schema.py`) and run in any environment.

CI runs:

```yaml
- run: docker compose -f config/docker-compose.yaml up -d
- run: ./scripts/wait_for_mysql.sh
- run: python -m pytest
```

## Consequences

**Good**

- Real test signal. Failed inserts due to FK or constraint issues fail
  fast.
- Local dev is one command (`docker compose up -d`). Same fixture in
  CI.
- Skip-gracefully behavior keeps the unit tier usable without Docker.

**Cost**

- ~10 second startup hit per CI run (MySQL warm-up). Acceptable.
- Docker is a hard prerequisite for full-suite testing. The README
  spells this out.
- Test DB schema lives in the same MySQL instance as a developer's
  real schema (different schema names). The `tests/conftest.py`
  picks `test_symphony_<random>` to avoid collision.

## Alternatives considered

- **`pytest-mysql`** (Python wrapper that downloads MySQL binaries).
  Considered; rejected because it doesn't match production MySQL flags
  closely enough and the Docker fixture is what the team already uses.
- **SQLite via DataJoint's experimental SQLite backend.** As of v2.0,
  the SQLite path doesn't have a JSON column type and named foreign keys behave
  differently — too many tests would behave differently from prod.
