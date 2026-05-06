# Testing Specification

**Status:** Stable
**Framework:** `pytest`
**DB:** Docker MySQL via `config/docker-compose.yaml` (graceful skip if unreachable)

## Layout

```
tests/
  conftest.py                 # fixtures (Docker MySQL, AppConfig, fresh schema, sample JSON)
  fixtures/
    sample_dj.json            # minimal but complete _dj.json (1 exp, 1 animal, 1 prep, 1 cell, 2 epochs)
    sample_tags.json          # matching tags sidecar
  test_config.py              # YAML loading + env-var precedence
  test_timestamps.py          # .NET ticks ↔ datetime
  test_schema.py              # schema instantiates, FKs declared, dj.Diagram renders
  test_ingest_unit.py         # JSON → tuple builder (no DB)
  test_ingest_integration.py  # full ingest into MySQL (skip if DB unreachable)
  test_query.py               # query helpers behave on the fixture data
  test_invariants.py          # the five DJ JSON invariants
```

`conftest.py` exposes:

| Fixture | Scope | Description |
|---|---|---|
| `app_config` | session | `AppConfig` pointing at the Docker MySQL |
| `mysql_available` | session | `True` if a connection succeeds; tests requiring DB use `pytest.importorskip` style guard |
| `db` | function | Fresh schema, drops all rows after the test (`schema.drop_quick()`) |
| `sample_json` | session | Loaded `fixtures/sample_dj.json` |
| `tmp_config_yaml` | function | A tmp YAML written from a dict, returned as Path |

## Running

```bash
# 1. Start Docker MySQL (one time)
cd config && docker compose up -d

# 2. Run the suite
cd ..
python -m pytest                    # all tests
python -m pytest -k "not integration"   # unit only, no DB needed
python -m pytest tests/test_schema.py   # schema only
```

CI runs `docker compose up -d`, waits for the healthcheck, then `pytest`.

## What each suite asserts

### `test_config.py`
- Default YAML loads to the documented `AppConfig` defaults.
- A YAML missing `paths:` falls back to the documented defaults.
- `DJ_HOST` overrides `database.host`.
- `DJ_PASSWORD` overrides `database.password`.
- An explicit `path` arg trumps the env var trumps `~/.datajoint_config.yaml`.
- Invalid YAML raises `ConfigError` with the file path in the message.

### `test_timestamps.py`
- `dotnet_ticks_to_datetime(637840584000000000) == datetime(2022,1,1,0,0,0,tzinfo=UTC)`.
- Round-trip: `datetime_to_dotnet_ticks(ticks_to_datetime(t)) == t` for 100 random ticks.
- Offset hours preserved through round-trip.

### `test_schema.py`
- `from symphony_dj.schema import declare; declare(schema_decorator)` runs without error against an in-memory mock connector.
- Every table's `definition` parses (DataJoint validates on declaration).
- Foreign-key graph matches [`01_schema.md`](01_schema.md): `Animal -> Experiment`, `Preparation -> Animal`, etc.
- Primary key types: every `*_uuid` PK is `varchar(36)`.
- `dj.Diagram(schema)` produces output (smoke test only — no visual check).

### `test_ingest_unit.py`
- Pure mapping tests, no DB. `build_experiment_tuple(json_obj) == expected_dict`.
- Tested for: Experiment, Animal, Preparation, Cell, EpochGroup, EpochBlock, Epoch, Response, Stimulus, Background.
- Tags JSON parsing produces the expected list of tag tuples.
- A JSON missing optional fields produces a tuple with `None` in the right places, not `KeyError`.

### `test_ingest_integration.py` (skips without DB)
- Ingest `fixtures/sample_dj.json`: row counts in each table match the JSON.
- Re-ingesting the same file is a no-op (row counts unchanged).
- Deleting an Experiment cascades to Animal/Preparation/.../Background.
- Concurrent ingest of the same file from two threads results in the same final row count (no duplicates, no errors).

### `test_query.py`
- `db.query.tree(uuid)` reproduces the `_dj.json` shape (modulo column renames) for the fixture.
- `db.query.epochs_for(protocol_id=...)` returns the right Epoch count.
- Tag CRUD is idempotent.
- `db.query.fields("epoch_block")` returns documented (name, type) tuples.

### `test_invariants.py` (skips without DB)
- All five DJ JSON invariants from [`02_ingestion.md`](02_ingestion.md#cross-validation-against-the-upstream-contract).

## CI gates

A change cannot be merged unless:

1. `pytest -k "not integration"` is green locally and in CI.
2. Integration tests are green when run against the Docker fixture.
3. `tests/test_invariants.py` passes — this is the contract check.
4. The schema spec ([`01_schema.md`](01_schema.md)) and the schema code
   declare the same set of tables (a `test_schema_spec_in_sync.py` test
   parses the spec's `### TableName` headings and the code's
   `dj.Manual` subclasses; they must match).

## When things go wrong

- **Docker MySQL won't start.** `cd config && docker compose logs`. The
  most common cause is a stale `mysql_data` volume; delete with
  `docker compose down -v` and retry.
- **`pytest` says `MySQL unavailable`, all integration tests skip.**
  `dj.config['database.host']` may be wrong. Check `app_config.database`
  in a REPL.
- **Schema collision (table already exists with different definition).**
  `db.schema.drop_quick()` in a Python shell, then re-run.
