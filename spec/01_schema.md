# DataJoint Schema Specification

**Status:** Stable (DataJoint 2.0)
**Schema name:** configurable (default `symphony`)
**Source contract:** [`DJ_JSON_SCHEMA.md`](../../Symphony-DAS/Symphony3/symphony3_testbed/spec/specs/DJ_JSON_SCHEMA.md)

This document specifies every table the library declares. Each table
maps directly to one entity in the DJ JSON hierarchy. Field naming
follows DataJoint conventions (`snake_case`, primary keys above the
`---` separator) and matches the underlying JSON keys where possible.

## Conventions

- **Primary key** for every Symphony entity is its UUID, stored as
  `varchar(36)`. This replaces the legacy `id: int auto_increment` +
  `h5_uuid: varchar(255)` split. See [ADR-0001](decisions/0001-uuid-primary-keys.md).
- **Foreign keys** follow DataJoint's standard `->` syntax. The parent's
  primary key is renamed in the child only when the child needs to
  disambiguate multiple parents (e.g., `EpochBlock` references both
  `EpochGroup` and `Protocol`).
- **JSON columns** hold pass-through metadata that doesn't get its own
  column. Required-by-the-app fields are promoted to columns; everything
  else lives in `properties: json`. DataJoint 2.0's `json` type uses
  MySQL's native `JSON` column and auto-encodes Python dicts on insert
  / decodes on fetch via the JSON category in `TYPE_PATTERN`. Raw
  `longblob` is recognised but not auto-encoded (PyMySQL refuses to
  escape a dict directly), and the legacy alias `blob` was removed in
  DataJoint 2.0.
- **Timestamps** are stored as `datetime(6)` (microsecond precision) in
  UTC. `*_offset_hours` columns preserve the original `.NET`
  `DateTimeOffset` offset so the local wall-clock time is recoverable.

## Schema diagram (logical)

```
                     ┌───────────┐
                     │ Protocol  │   (Lookup; protocol_id strings)
                     └─────▲─────┘
                           │
┌────────────┐  ┌──────────┴────────┐  ┌────────────┐
│ Experiment │──│   EpochBlock      │──│SortingChunk│ (analysis)
└─────┬──────┘  └─────▲─────────────┘  └─────▲──────┘
      │                │                     │
      ▼                │                     │
┌────────────┐         │                     │
│  Animal    │         │                     │
└─────┬──────┘         │                     │
      ▼                │                     │
┌────────────┐         │                     │
│Preparation │         │                     │
└─────┬──────┘         │                     │
      ▼                │                     │
┌────────────┐         │                     │
│   Cell     │         │                     │
└─────┬──────┘         │                     │
      ▼                │                     │
┌────────────┐         │                     │
│ EpochGroup │─────────┘                     │
└────────────┘                               │
              ┌─────────────┐  ┌──────────┐  │
              │   Epoch     │──│Response  │  │
              └─────┬───────┘  ├──────────┤  │
                    ▼          │Stimulus  │  │
              ┌──────────┐     ├──────────┤  │
              │  Note    │     │Background│  │
              ├──────────┤     └──────────┘  │
              │   Tag    │                   │
              └──────────┘                   │
                                  ┌──────────┴────┐
                                  │  SortedCell   │
                                  └──────────┬────┘
                                             ▼
                                  ┌─────────────────┐
                                  │CellTypeFile     │
                                  ├─────────────────┤
                                  │SortedCellType   │
                                  └─────────────────┘
```

## Table specifications

### `Protocol` (Lookup)

```
protocol_id : varchar(255)   # Symphony protocolID, e.g. "manookinlab.protocols.SpatialNoise"
---
display_name = NULL : varchar(255)
description = NULL : varchar(1024)
```

`protocol_id` is the canonical Symphony protocol string. The library
inserts a row the first time it ingests an `EpochBlock` referencing it.

### `Experiment` (Manual)

```
experiment_uuid : varchar(36)
---
purpose = NULL : varchar(255)
start_time = NULL : datetime(6)
start_offset_hours = NULL : float
end_time = NULL : datetime(6)
end_offset_hours = NULL : float
keywords = NULL : varchar(1024)         # comma-separated
experimenter = NULL : varchar(255)
institution = NULL : varchar(255)
lab = NULL : varchar(255)
project = NULL : varchar(255)
rig = NULL : varchar(255)
rig_type = NULL : enum('PATCH','MEA')
h5_path = NULL : varchar(1023)          # path to source .h5 (optional)
json_path = NULL : varchar(1023)        # path to source _dj.json (optional)
date_added = CURRENT_TIMESTAMP : timestamp
properties : json                   # full passthrough properties dict
```

`experiment_uuid` is the UUID of the root `experiment-{uuid}` HDF5
group. (DJ JSON's top-level Experiment object exposes this via
`metadata['sources'][0]`'s `uuid`.)

### `Animal` (Manual)

```
animal_uuid : varchar(36)
---
-> Experiment
label = NULL : varchar(255)
start_time = NULL : datetime(6)
start_offset_hours = NULL : float
animal_id = NULL : varchar(255)         # the lab's ID (e.g. "A1")
description = NULL : varchar(1024)
sex = NULL : varchar(32)
age = NULL : varchar(64)
weight = NULL : varchar(64)
dark_adaptation = NULL : varchar(255)
species = NULL : varchar(255)
properties : json
```

### `Preparation` (Manual)

```
preparation_uuid : varchar(36)
---
-> Animal
label = NULL : varchar(255)
start_time = NULL : datetime(6)
start_offset_hours = NULL : float
bath_solution = NULL : varchar(255)
preparation_type = NULL : varchar(255)
region = NULL : varchar(255)
array_pitch = NULL : varchar(32)        # "30um" / "60um" / "120um"
properties : json
```

### `Cell` (Manual)

```
cell_uuid : varchar(36)
---
-> Preparation
label = NULL : varchar(255)
start_time = NULL : datetime(6)
start_offset_hours = NULL : float
cell_type = NULL : varchar(255)
properties : json
```

### `EpochGroup` (Manual)

```
epoch_group_uuid : varchar(36)
---
-> Cell
label = NULL : varchar(255)
start_time = NULL : datetime(6)
start_offset_hours = NULL : float
end_time = NULL : datetime(6)
end_offset_hours = NULL : float
keywords = NULL : varchar(1024)
properties : json
```

### `EpochBlock` (Manual)

```
epoch_block_uuid : varchar(36)
---
-> EpochGroup
-> Protocol
data_file = NULL : varchar(1023)        # MEA .h5 path (relative); blank for patch
start_time = NULL : datetime(6)
start_offset_hours = NULL : float
end_time = NULL : datetime(6)
end_offset_hours = NULL : float
parameters : json                   # protocolParameters/* attribute pass-through
properties : json                   # epochStarts, frameTimesMs, array_id, n_samples, ...
```

### `Epoch` (Manual)

```
epoch_uuid : varchar(36)
---
-> EpochBlock
start_time = NULL : datetime(6)
start_offset_hours = NULL : float
end_time = NULL : datetime(6)
end_offset_hours = NULL : float
is_partial = 0 : tinyint
keywords = NULL : varchar(1024)
parameters : json                   # per-epoch protocol parameters
properties : json
```

### `Response` (Manual; per-epoch, per-device)

```
-> Epoch
device_name : varchar(127)
---
sample_rate = NULL : double
sample_rate_units = NULL : varchar(31)
input_time = NULL : datetime(6)
input_offset_hours = NULL : float
units = NULL : varchar(31)
h5path = NULL : varchar(1023)           # path inside the .h5 to "data" dataset
properties : json
```

`Response` rows are pure metadata. Raw sample arrays are not duplicated
into MySQL — they stay in the H5 and are fetched on demand via
`symphony_dj.h5io.read_response_data(uuid)`.

### `Stimulus` (Manual; per-epoch, per-device)

```
-> Epoch
device_name : varchar(127)
---
stimulus_id = NULL : varchar(255)
sample_rate = NULL : double
sample_rate_units = NULL : varchar(31)
units = NULL : varchar(31)
duration_seconds = NULL : double
h5path = NULL : varchar(1023)
params : json                       # generator params (param_*)
properties : json
```

### `Background` (Manual; per-epoch, per-device)

```
-> Epoch
device_name : varchar(127)
---
value = NULL : double
value_units = NULL : varchar(31)
sample_rate = NULL : double
sample_rate_units = NULL : varchar(31)
properties : json
```

### `Note` (Manual)

```
note_id : int unsigned auto_increment
---
entity_table : varchar(63)              # 'experiment', 'epoch', ...
entity_uuid : varchar(36)
note_time = NULL : datetime(6)
note_offset_hours = NULL : float
text : varchar(4095)
```

### `Tag` (Manual)

```
tag_id : int unsigned auto_increment
---
entity_table : varchar(63)
entity_uuid : varchar(36)
-> Experiment                           # for partition / cascade
user : varchar(63)
tag : varchar(255)
unique index (entity_uuid, user, tag)
```

`Tag` rows are user-applied annotations, not experimental metadata.
They're separate from `properties` so they can be added/removed without
re-ingesting.

### Analysis tables (carried forward from legacy)

```
SortingChunk
  sorting_chunk_id : int unsigned auto_increment
  ---
  -> Experiment
  chunk_name : varchar(255)
  unique index (experiment_uuid, chunk_name)

SortedCell
  sorted_cell_id : int unsigned auto_increment
  ---
  -> SortingChunk
  algorithm : varchar(127)
  cluster_id : int

CellTypeFile
  cell_type_file_id : int unsigned auto_increment
  ---
  -> SortingChunk
  algorithm : varchar(127)
  file_name : varchar(255)

SortedCellType
  -> SortedCell
  -> CellTypeFile
  ---
  cell_type : varchar(127)
```

`EpochBlock` also gets a nullable `-> [nullable] SortingChunk` to allow
linking a block to its sorted output.

## Differences vs. the legacy schema (`/old/schema.py`)

| Legacy | New | Why |
|---|---|---|
| `id: int auto_increment` + `h5_uuid: varchar(255)` | `*_uuid: varchar(36)` (single PK) | UUIDs are stable across re-ingestion and removable-host moves; the dual-key pattern was bookkeeping the schema didn't need. |
| `properties: json` (legacy) | `properties: json` (kept) | The legacy schema actually had this right. DataJoint 2.0 has first-class JSON support: declaring `: json` uses MySQL's native JSON column type and auto-encodes Python dicts via the JSON category in `TYPE_PATTERN`. The 0.x-era `blob` alias has been removed. |
| `parent_id` + projected FK aliasing (`Experiment.proj(parent_id='id')`) | Direct `-> ParentTable` | One canonical FK per relationship. The ambiguous-aliased style was hard to query and forced manual join logic in `query.py`. |
| No `Background` table | First-class `Background` | DJ JSON exposes per-device backgrounds; legacy code dropped them. |
| Raw `tag` field as comma-separated string | One `Tag` row per `(entity, user, tag)` | Allows native DJ filtering and removes string parsing in the query layer. |
| Hard-coded `start_time` parsed from `MM/DD/YYYY HH:MM:SS:ffffff` strings | Native `datetime(6)` + `*_offset_hours` | Avoids re-parsing on every query; preserves DST/timezone via the offset. |

## Migration

This is a clean schema, not an in-place migration of the old database.
If you have an existing legacy MySQL instance, `docs/migration_v2.md`
documents the recommended workflow (re-ingest from the JSON files; the
H5 → JSON path is the source of truth, not the old MySQL rows).
