# `datajoint_symphony` — Spec Index

This directory holds the spec-driven design for the Symphony → DataJoint
pipeline. Specs here are the **source of truth**; code in `src/python/`,
`scripts/`, `docs/`, and `tests/` is expected to conform to them. Any
behavioral change should land here first (or alongside the code change),
not after.

## Pipeline at a glance

```
Symphony H5 (.h5)            ── canonical raw data + metadata
        │
        ▼  parse_data.py  (manookin-lab/MEA/database/)
DJ JSON  (<exp>_dj.json)     ── canonical metadata export
        │
        ▼  symphony_dj.ingest
DataJoint (MySQL)            ── queryable relational schema
        │
        ▼  symphony_dj.query / Jupyter
Analysis
```

All three formats share **UUIDs**: every entity in the DataJoint schema
keys on the same UUID that identifies it in the H5 file and the
`_dj.json` document. This makes the three layers losslessly cross-
referenceable without the bookkeeping `id` / `h5_uuid` split that lived
in the legacy schema.

## Upstream contracts (read-only references)

Two specs in the **Symphony** repo define what we receive:

- [`H5_SCHEMA.md`](../../Symphony-DAS/Symphony3/symphony3_testbed/spec/specs/H5_SCHEMA.md)
  — the on-disk HDF5 layout (`experiment-{uuid}/sources/...`,
  `epochGroups/...`, etc.).
- [`DJ_JSON_SCHEMA.md`](../../Symphony-DAS/Symphony3/symphony3_testbed/spec/specs/DJ_JSON_SCHEMA.md)
  — the JSON document `parse_data.py` emits (`*_dj.json`). This is the
  direct input to ingestion.

These are upstream contracts; this project does not modify them. We
align *to* them.

## Specs in this directory

| File | Purpose |
|---|---|
| [`00_overview.md`](00_overview.md) | System goals, components, dataflow |
| [`01_schema.md`](01_schema.md) | DataJoint schema spec (tables, keys, FKs) |
| [`02_ingestion.md`](02_ingestion.md) | DJ JSON → DataJoint ingestion contract |
| [`03_configuration.md`](03_configuration.md) | `datajoint_config.yaml` schema, env vars, precedence |
| [`04_query_api.md`](04_query_api.md) | Python/Jupyter query API |
| [`05_testing.md`](05_testing.md) | Test layout, Docker MySQL fixture, CI gates |

## Decision records

ADR-style decisions (what we chose and why) live under
[`decisions/`](decisions). New decisions get the next sequential
number. Old decisions are amended via a follow-up ADR, not in place.

| ADR | Title |
|---|---|
| [0001](decisions/0001-uuid-primary-keys.md) | UUID as the primary key for every Symphony entity |
| [0002](decisions/0002-datajoint-v20-migration.md) | Migrate to DataJoint 2.0 conventions |
| [0003](decisions/0003-yaml-configuration.md) | YAML configuration with env-var overrides |
| [0004](decisions/0004-pytest-docker-mysql.md) | pytest + Docker MySQL for tests |
| [0005](decisions/0005-drop-flask-rest.md) | Drop the Flask REST surface; library + CLI only |

## How to evolve a spec

1. Open a draft change here. Reference it from your branch / PR.
2. Update or add an ADR if the change reverses a prior decision.
3. Update affected code, scripts, docs, and tests in the same change.
4. CI runs `tests/` — schema validity, ingestion roundtrip, and config
   loading must pass before merge.
