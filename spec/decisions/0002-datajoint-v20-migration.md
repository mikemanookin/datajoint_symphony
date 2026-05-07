# ADR 0002 — Migrate to DataJoint 2.0 conventions

**Status:** Accepted
**Date:** 2026-05-06
**Reference:** https://docs.datajoint.com/how-to/migrate-to-v20/

## Context

The legacy code targeted DataJoint 0.13/0.14. Patterns that worked then
either no longer work in 2.0 or are deprecated:

- `dj.schema('schema')` (lowercase factory). Still callable in 2.0 but
  the documented form is `dj.Schema(name)`.
- `properties: json` columns. DataJoint 2.0 has **first-class JSON
  support**: declaring an attribute as `: json` uses MySQL's native
  `JSON` column type and auto-encodes/decodes Python dicts via the
  JSON category in `TYPE_PATTERN`. The legacy `blob` alias was removed
  in 2.0 (only `bytes`, `tinyblob…longblob`, `<adapter>`, and external
  blob stores like `blob@store` are recognised); raw `longblob` skips
  the encoder, which causes ``TypeError: dict can not be used as
  parameter`` on insert. So the **legacy schema's `: json` was already
  correct** — we kept it. PostgreSQL portability is a non-goal for
  this project (we run MySQL-only).
- `dj.conn().connect()` followed by `dj.config['database.host'] = ...`.
  In 2.0 the recommended order is `dj.config.update({...})` *before*
  `dj.conn()`, and `dj.conn()` returns the cached connection.
- `Manual.insert1` with a dict where the JSON value is a numpy array
  worked by luck in 0.x; in 2.0 it must be cast to a list/tuple.
- `dj.U().aggr(table, max=...)` for getting `max(id)` — still works,
  but with UUID PKs we no longer need it.

## Decision

The new code targets DataJoint **2.0** exclusively. Compatibility with
older versions is not a goal.

Concretely:

- `dj.Schema(name)` is the schema factory; `dj.schema(...)` is not used.
- Connections are opened via `dj.config.update({...}); dj.conn()`,
  centralized in `symphony_dj.connection.connect()`.
- All "open metadata" columns (`properties`, `parameters`, `params`) are `json`. DataJoint 2.0 maps this to MySQL's native JSON column type with automatic dict encode/decode.
- `insert(..., skip_duplicates=True)` is the standard idempotency hook
  (documented v2.0 API).
- `dj.Diagram(schema)` is used for ER diagrams in docs/notebooks.
- Schema is declared by passing the `dj.Schema` decorator into a
  `declare(schema)` factory function — this is the v2.0-recommended
  pattern for parametric schema names (lets the YAML pick the schema
  name).

## Consequences

**Good**

- Future-proof. New DataJoint releases land cleanly.
- Idiomatic. New contributors who know DataJoint 2.0 read this code
  without having to mentally translate older patterns.
- Tooling support. `dj.Diagram` and `dj.list_schemas()` work as
  documented.

**Cost**

- The legacy app stops working as-is. We mitigate by leaving
  `old/app.py` and `old/schema.py` in the repo as reference, and by
  documenting the migration in [`docs/migration_v2.md`](../../docs/migration_v2.md).
- `json` columns are MySQL JSON, so raw-SQL clients can read them
  directly (`SELECT properties->'$.lab' FROM experiment`). This is an
  improvement over the 0.x `longblob+pickle` pattern, which produced
  binary blobs that only Python could decode.

## Alternatives considered

- **Stay on DataJoint 0.x.** Cuts the migration cost but leaves the
  team on a deprecated stack; new MEA tooling already targets 2.0.
- **Use SQLAlchemy directly.** Drops the DataJoint conventions
  entirely. Considered briefly; rejected because DataJoint's
  expression-tree query language is what makes notebook work tractable
  for the lab.
