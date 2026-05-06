# Ingestion Specification

**Status:** Stable
**Input:** `*_dj.json` (see [`DJ_JSON_SCHEMA.md`](../../Symphony-DAS/Symphony3/symphony3_testbed/spec/specs/DJ_JSON_SCHEMA.md))
**Output:** rows in the DataJoint schema defined in [`01_schema.md`](01_schema.md)

This spec is the **field-level mapping** from a DJ JSON document to
DataJoint rows, plus the rules that govern idempotency, partial files,
and error recovery.

## Public surface

```python
from symphony_dj import connect

db = connect()                                        # uses datajoint_config.yaml
db.ingest_json("/path/to/20260410H_dj.json")          # one experiment
db.ingest_directory("/path/to/json_root/")            # batch ingest
```

Both calls return an `IngestReport` with counts of rows inserted per
table and any per-file errors. Both are safe to re-run.

## Ordering

Rows are inserted top-down so foreign keys are always satisfied:

1. `Protocol` (lookup; insert distinct `protocolID` values first)
2. `Experiment` (one row per `_dj.json`)
3. `Animal` (per `experiment.animals[]`)
4. `Preparation` (per `animal.preparations[]`)
5. `Cell` (per `preparation.cells[]`)
6. `EpochGroup` (per `cell.epoch_groups[]`)
7. `EpochBlock` (per `epoch_group.epoch_blocks[]`)
8. `Epoch` (per `epoch_block.epochs[]`)
9. `Response`, `Stimulus`, `Background` (per `epoch.responses/stimuli/backgrounds`)
10. `Tag` (if a sidecar tags file is provided)

Each level is inserted with `insert(..., skip_duplicates=True)` so
re-ingesting a partial file fills in only the missing rows.

## Field-level mapping

### Experiment

| DJ JSON field | DataJoint column | Notes |
|---|---|---|
| `metadata['sources'][0]['attributes']['uuid']` | `experiment_uuid` | PK |
| `metadata['sources'][0]['attributes']['purpose']` | `purpose` | optional |
| `startTimeDotNetDateTimeOffsetTicks` (+ offset hours) | `start_time`, `start_offset_hours` | converted via `timestamps.ticks_to_datetime` |
| `endTimeDotNetDateTimeOffsetTicks` | `end_time`, `end_offset_hours` | optional |
| `keywords` | `keywords` | comma-joined if list |
| `properties.experimenter`/`institution`/`lab`/`project`/`rig` | dedicated columns | promoted out of `properties` |
| `rig_type` (synthesized; `'MEA'` if `mea_raw_data_path`, else `'PATCH'`) | `rig_type` | from `parse_data.Symphony2Reader.create_symphony_dict` |
| `properties` (full dict) | `properties` (longblob) | full pass-through |

The `h5_path` and `json_path` columns are filled by the ingestor with
the absolute path it was handed. They are recorded only — never used as
part of any key — and may be NULL if the caller doesn't pass them.

### Animal

| DJ JSON | DataJoint | Notes |
|---|---|---|
| `animal['uuid']` | `animal_uuid` | PK |
| (parent experiment uuid) | `experiment_uuid` | FK |
| `animal['label']` | `label` | "A1", "A2", ... |
| `creationTimeDotNetDateTimeOffsetTicks` (+ offset) | `start_time`, `start_offset_hours` | |
| `animal['properties'].id`/`description`/`sex`/`age`/`weight`/`darkAdaptation`/`species` | dedicated columns | |
| `animal['properties']` (full) | `properties` | |

### Preparation

| DJ JSON | DataJoint | Notes |
|---|---|---|
| `preparation['uuid']` | `preparation_uuid` | PK |
| (parent animal uuid) | `animal_uuid` | FK |
| `preparation['label']` | `label` | "OD", "OS", ... |
| `properties.bathSolution` | `bath_solution` | |
| `properties.preparation` | `preparation_type` | NB. JSON key is singular `preparation` |
| `properties.region` | `region` | |
| `arrayPitch` (set by `parse_data.py` from group-level `array_id`) | `array_pitch` | |

### Cell

| DJ JSON | DataJoint | Notes |
|---|---|---|
| `cell['uuid']` | `cell_uuid` | PK |
| (parent preparation uuid) | `preparation_uuid` | FK |
| `cell['label']` | `label` | "cell1", ... |
| `properties.type` | `cell_type` | |

### EpochGroup

| DJ JSON | DataJoint | Notes |
|---|---|---|
| `epoch_group['uuid']` | `epoch_group_uuid` | PK |
| (parent cell uuid) | `cell_uuid` | FK |
| `epoch_group['label']` | `label` | |
| `startTime...`/`endTime...` | `start_time`/`end_time` (+ offsets) | |
| `keywords` | `keywords` | comma-joined |

### EpochBlock

| DJ JSON | DataJoint | Notes |
|---|---|---|
| `epoch_block['uuid']` | `epoch_block_uuid` | PK |
| (parent epoch_group uuid) | `epoch_group_uuid` | FK |
| `epoch_block['protocolID']` | `protocol_id` | FK; auto-inserted into `Protocol` if new |
| `epoch_block['dataFile']` | `data_file` | empty for patch |
| `startTime...`/`endTime...` | `start_time`/`end_time` (+ offsets) | |
| `epoch_block['parameters']` | `parameters` | longblob, byte-exact pass-through |
| `epoch_block['properties']` | `properties` | longblob; includes `epochStarts`, `frameTimesMs`, `array_id`, `n_samples` |

### Epoch

| DJ JSON | DataJoint | Notes |
|---|---|---|
| `epoch['uuid']` | `epoch_uuid` | PK |
| (parent epoch_block uuid) | `epoch_block_uuid` | FK |
| `epoch['start_time']`/`epoch['end_time']` (ISO 8601) | `start_time`/`end_time` | parsed via `datetime.fromisoformat` |
| (epoch's offset, derived from start_time) | `start_offset_hours`/`end_offset_hours` | |
| `epoch['parameters']` | `parameters` | per-epoch protocol params |
| `epoch.get('isPartial', False)` | `is_partial` | |
| `epoch['properties']` | `properties` | |
| `epoch['keywords']` (if present) | `keywords` | |

### Response / Stimulus / Background

For each `device_name → record` entry under `epoch.responses`,
`epoch.stimuli`, `epoch.backgrounds`:

| DJ JSON | DataJoint | Notes |
|---|---|---|
| (epoch uuid) | `epoch_uuid` | FK; part of compound PK |
| key | `device_name` | "Amp1", "Frame Monitor", ... |
| `sampleRate` | `sample_rate` | double |
| `sampleRateUnits` | `sample_rate_units` | "Hz" usually |
| `units` | `units` | response/stimulus units |
| `inputTimeDotNetDateTimeOffsetTicks` (response) | `input_time`/`input_offset_hours` | |
| `stimulusID` (stimulus) | `stimulus_id` | |
| `value`/`valueUnits` (background) | `value`/`value_units` | |
| (synthesized) | `h5path` | `experiment-{exp}/.../epoch-{epoch}/responses/{device}/data` |

### Tags (sidecar JSON, optional)

A separate `_tags.json` file (legacy format: `{ uuid: { tags: [[user, tag], ...] } }`)
yields one `Tag` row per `(uuid, user, tag)` tuple. Tags are only
inserted for entities present in the DataJoint schema; unknown UUIDs
are logged and skipped.

## Idempotency rules

Every insert uses **DataJoint's `skip_duplicates=True`**, with the UUID
as primary key. This means:

- Re-ingesting the same `_dj.json` is a no-op.
- A partially-ingested file (process killed mid-experiment) can be
  re-run; it'll fill in the rest.
- Two concurrent ingestors writing the same file are safe (DataJoint
  serializes via MySQL transactions). Last writer doesn't clobber: any
  conflicting field is ignored, not overwritten.

To **change** an existing row's metadata, the user must explicitly
delete the row first (`db.Experiment & "experiment_uuid='...'").delete()`
and re-ingest. The library never silently overwrites — that's the
escape hatch from accidental data loss.

## Error handling

- **Malformed JSON / schema mismatch** — the ingest aborts the whole
  file, leaves no partial rows for that experiment (DataJoint handles
  this via a single transaction at experiment scope), and the
  `IngestReport` records the error.
- **Missing parent** — should not happen given the JSON structure, but
  if it does (e.g., a pre-promoted Cell with no Preparation),
  the row is skipped and an error logged.
- **Tag for unknown UUID** — logged, skipped.
- **Database disconnection mid-ingest** — DataJoint raises; the
  ingestor lets the exception bubble up. The transaction at experiment
  scope rolls back; user re-runs.

## Cross-validation against the upstream contract

`tests/test_ingest_invariants.py` enforces the [DJ JSON
invariants](../../Symphony-DAS/Symphony3/symphony3_testbed/spec/specs/DJ_JSON_SCHEMA.md#invariants):

1. UUID consistency — every DataJoint row's PK matches its source
   UUID.
2. Completeness — round-trip count of every entity in the JSON equals
   the row count in DataJoint after ingestion.
3. Protocol fidelity — `EpochBlock.parameters` and `Epoch.parameters`
   in DataJoint deserialize to dicts equal to the JSON's.
4. Device name format — short names ("Amp1") only, never UUID-suffixed.
5. Timestamp roundtrip — ticks → datetime → ticks recovers the original
   ticks (modulo 1-µs floor).

These tests run in CI against the Docker MySQL fixture.
