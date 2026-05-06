# Schema Reference

This is a user-facing summary of the tables and columns the library
declares. The authoritative spec is [`spec/01_schema.md`](../spec/01_schema.md);
diff against that file when you're investigating a column-level
question.

## Table-by-table summary

### `Protocol` (Lookup)

`protocol_id` is the canonical Symphony protocol string
(`manookinlab.protocols.SpatialNoise`). Auto-inserted by ingestion.

### `Experiment`

One row per Symphony HDF5 file. PK: `experiment_uuid`.

Notable columns:

- `experimenter`, `lab`, `institution`, `project`, `rig` — promoted from
  `properties` for cheap filtering.
- `rig_type` — enum: `'PATCH' | 'MEA'`.
- `h5_path`, `json_path` — origin file paths, recorded by ingestion.
- `properties` — full pass-through of the JSON's `properties` dict.

### `Animal` → `Preparation` → `Cell` → `EpochGroup`

Each level keys on its own UUID and FKs to the parent. Standard fields:

- `label` — the human-friendly name (`"A1"`, `"OD"`, `"cell1"`, ...).
- `start_time` + `start_offset_hours` — preserved from the source's
  `creationTimeDotNetDateTimeOffsetTicks` pair.
- Per-level promoted columns: `Animal.species/sex/age/weight/...`,
  `Preparation.bath_solution/preparation_type/region/array_pitch`,
  `Cell.cell_type`.
- `properties` — full dict from JSON.

### `EpochBlock`

PK: `epoch_block_uuid`. FKs to `EpochGroup` and `Protocol`.

- `data_file` — relative path to the MEA `.h5` (empty for patch).
- `parameters` — the `protocolParameters/` attribute dict, byte-exact.
- `properties` — includes derived block-level fields:
  `epochStarts`, `epochEnds`, `frameTimesMs`, `array_id`, `n_samples`.

### `Epoch`

PK: `epoch_uuid`. Per-epoch parameters and timestamps.

### `Response` / `Stimulus` / `Background`

Compound PK `(epoch_uuid, device_name)`. Per-device metadata only — the
raw sample arrays stay in the source HDF5 and are read on demand via
`symphony_dj.h5io.read_response_data()`.

### `Note`

Free-text experimenter notes, attached to any entity by
`(entity_table, entity_uuid)`.

### `Tag`

User-applied tags on any entity. Unique by `(entity_uuid, user, tag)`.
Adding the same tag twice is a no-op. Tags are independent of
ingestion — they survive re-ingest of the same JSON.

### Analysis tables

`SortingChunk`, `SortedCell`, `CellTypeFile`, `SortedCellType` mirror
the legacy structure. Populated by external spike-sorting / cell-typing
pipelines, not by JSON ingestion.

## Diagram

To render the ER diagram in a notebook:

```python
import datajoint as dj
from symphony_dj import connect

db = connect()
dj.Diagram(db.schema)
```

(Requires `pip install pydot graphviz` and the system `graphviz`.)

## Renaming and migration

The legacy schema in `old/schema.py` used `id: int auto_increment` +
`h5_uuid: varchar(255)` on every table. The new schema collapses these
to a single UUID PK. See [`migration_v2.md`](migration_v2.md) for the
mapping table and re-ingestion workflow.
