# ADR 0001 — UUID as the primary key for every Symphony entity

**Status:** Accepted
**Date:** 2026-05-06

## Context

The legacy schema (`old/schema.py`) used a dual-key pattern on every
table:

```
Experiment
  id : int auto_increment    # the "DataJoint id"
  ---
  h5_uuid : varchar(255)     # the "real" identity
  ...
```

Children referenced parents by `parent_id` (an alias of the parent's
`id`), and queries had to join through the `id ↔ h5_uuid` mapping
whenever they crossed the JSON / DB boundary.

Three things made this painful:

1. **Re-ingestion broke identity.** Dropping an experiment and
   re-ingesting from JSON gave it a fresh `id`. Anything that had
   recorded the old `id` (saved queries, sorted-cell tables, external
   notebooks) now pointed at a row that didn't exist or — worse — at a
   different row.
2. **Two sources of truth.** Code had to remember whether it was
   talking about the DJ id or the H5 UUID. `helpers/pop.py` did this
   inconsistently (sometimes `experiment_id`, sometimes
   `Experiment.proj(experiment_id='id')`).
3. **The H5 UUID was unique already.** The whole upstream pipeline (H5,
   `_dj.json`, `parse_data.py`) is keyed by UUID. The DJ id was extra.

## Decision

Every Symphony entity's primary key in DataJoint is its UUID, stored as
`varchar(36)`. The dual-key pattern is dropped.

```
Experiment
  experiment_uuid : varchar(36)
  ---
  ...

Animal
  animal_uuid : varchar(36)
  ---
  -> Experiment              # FK by experiment_uuid
  ...
```

## Consequences

**Good**

- Re-ingestion is identity-preserving. The same JSON yields the same
  primary keys. Saved queries, sorted-cell links, notebooks all keep
  working.
- One source of truth. `epoch_uuid` means the same thing everywhere —
  in the H5 file, in the JSON, in the DB.
- Foreign keys are direct (`-> Animal`) — no aliasing.

**Cost**

- 36-byte string PKs are larger than int PKs. For our scale (~1e6
  epochs/year/lab) this is irrelevant; MySQL's storage and index size
  costs are well within hardware.
- The legacy DB is not portable as-is. Anyone with old data must
  re-ingest from the original `_dj.json` files (which they have, by
  spec). [`docs/migration_v2.md`](../../docs/migration_v2.md) walks
  through this.

## Alternatives considered

- **Keep the `id` PK, demote `h5_uuid` to a unique index.** Half-fixes
  the identity problem (a unique-by-UUID upsert is possible) but doesn't
  solve the two-sources-of-truth issue, and requires every external
  consumer to keep re-resolving UUID → id.
- **Use UUID-as-binary (`binary(16)`) for storage efficiency.** A real
  win on row size, but DataJoint expressions become harder to read and
  hand-write (`UNHEX(REPLACE(uuid,'-',''))` everywhere). For the lab's
  scale this isn't worth the ergonomic cost.
