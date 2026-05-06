# Overview

`datajoint_symphony` is a Python library + CLI that ingests Symphony 3
metadata into a DataJoint (MySQL) schema and lets users query it from
plain Python, Jupyter, or scripts. It is **not** a UI; it intentionally
has no Flask / REST surface (see [ADR-0005](decisions/0005-drop-flask-rest.md)).

## Goals

1. **Faithful** — the relational schema is a 1:1 lossless projection of
   `_dj.json`'s entity hierarchy. Round-trip from H5 → JSON → DJ → query
   recovers the original metadata fields.
2. **Idempotent** — re-ingesting the same JSON file is a no-op.
3. **Configurable** — all environment-specific values (DB host,
   credentials, NAS paths) live in YAML or env vars, never in code.
4. **Testable** — the package boots against a Dockerized MySQL via a
   single `docker compose up`, and pytest exercises every public
   function.
5. **DataJoint 2.0 idiomatic** — uses the v2.0 API
   (`dj.Schema(...)`, `dj.config["database.use_tls"]` defaults, etc.)
   and avoids deprecated patterns.

## Non-goals

- No web frontend, REST endpoints, or background job system. Users drive
  the library from Jupyter or `python -m symphony_dj`.
- No spike-sorting / waveform analysis logic. Those live in MEA-side
  pipelines and write *their* outputs into auxiliary tables this library
  defines (`SortingChunk`, `SortedCell`, etc.); the library does not
  perform sorting.
- No HDF5 → JSON conversion. That is `parse_data.py`'s job, upstream.
  This library treats `_dj.json` as its input contract.

## Components

```
                         ┌──────────────────────────┐
                         │   datajoint_config.yaml  │
                         │   $DJ_HOST, $DJ_USER...  │
                         └────────────┬─────────────┘
                                      │
                                      ▼
   _dj.json   ─────►  symphony_dj.ingest  ──────►  MySQL (DataJoint)
                          │     │                      ▲
                          │     └─► symphony_dj.schema │
                          │                            │
                          ▼                            │
                   symphony_dj.connection ◄────────────┘
                          ▲
                          │
   .h5 file  ─────►  symphony_dj.h5io       (raw samples on demand)
                          ▲
                          │
                  symphony_dj.query   ◄────  Jupyter / scripts
```

| Module | Responsibility |
|---|---|
| `symphony_dj.config` | Load YAML, apply env-var overrides, return a typed `AppConfig`. |
| `symphony_dj.connection` | Open `dj.conn()`, instantiate the `dj.Schema`, return live table classes. |
| `symphony_dj.schema` | Declare every `dj.Manual` / `dj.Lookup` / `dj.Computed` table. |
| `symphony_dj.timestamps` | Convert `.NET` ticks (Symphony's native time) ↔ `datetime`. |
| `symphony_dj.ingest` | Parse a `_dj.json` and insert rows. Idempotent. |
| `symphony_dj.h5io` | Resolve a UUID → raw response/stimulus samples in the source H5. |
| `symphony_dj.query` | Convenience helpers for hierarchy traversal, downloads, tag IO. |
| `symphony_dj.cli` | `python -m symphony_dj {init,ingest,query,...}`. |

## Dataflow walkthrough

1. **Configure.** A user copies `config/datajoint_config.yaml` to
   `~/.datajoint_config.yaml`, fills in DB host/user/password and JSON
   paths. Or sets `DJ_HOST`, `DJ_USER`, `DJ_PASSWORD`, etc.

2. **Connect.** `from symphony_dj import connect` then
   `db = connect()`. Internally this calls `dj.config.update(...)` and
   `dj.conn().connect()`, then declares the schema if missing and
   returns a `Database` handle.

3. **Ingest.** `db.ingest_json("/path/to/20260410H_dj.json")` inserts
   `Experiment → Animal → Preparation → Cell → EpochGroup → EpochBlock
   → Epoch → (Response, Stimulus, Background)`, each keyed by its
   upstream UUID. Re-running the call is a no-op for rows already
   present.

4. **Query.** `(db.Epoch & {"protocol_id": "manookinlab.protocols.SpatialNoise"}).fetch()`
   works directly. The `db.query` helpers add tree-shaped traversal,
   batched downloads, and tag CRUD.

## Versioning of the spec

The format is governed by upstream specs:

- **H5 PersistenceVersion 2** (Symphony) — see `H5_SCHEMA.md`.
- **DJ JSON** — see `DJ_JSON_SCHEMA.md`.

This library's schema follows those specs. If upstream bumps a version,
update [`01_schema.md`](01_schema.md) and the ingestion mapping
([`02_ingestion.md`](02_ingestion.md)) **first**, then the code, then
add a migration note under [`docs/migration_v2.md`](../docs/migration_v2.md).
