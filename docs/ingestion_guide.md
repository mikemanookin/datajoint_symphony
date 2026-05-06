# Ingestion Guide

Walking through the JSON-to-DataJoint ingest workflow. The formal spec
is in [`spec/02_ingestion.md`](../spec/02_ingestion.md).

## Inputs

- `*_dj.json` — the canonical Symphony metadata export emitted by
  `parse_data.py`. The format is fully specified in the Symphony repo's
  `DJ_JSON_SCHEMA.md`.
- *(optional)* a tags sidecar JSON (legacy format
  `{ uuid: { tags: [[user, tag], ...] } }`).

The library does **not** convert HDF5 → JSON. Run `parse_data.py` first.

## One file

```bash
python -m symphony_dj ingest /Volumes/data/data/json/20260410H_dj.json
# or
python scripts/02_ingest_json.py /Volumes/data/data/json/20260410H_dj.json
```

Or programmatically:

```python
from symphony_dj import connect
with connect() as db:
    report = db.ingest_json("/Volumes/data/data/json/20260410H_dj.json")
    print(report)
```

`report` is an `IngestReport` with per-table row counts and an `errors`
list.

## A whole directory

```bash
python -m symphony_dj ingest /Volumes/data/data/json/
```

Files are matched by `*_dj.json` (recursively). Failures on individual
files don't stop the batch — they're recorded in the report.

## Idempotency

Every insert uses `skip_duplicates=True` against a UUID primary key. So:

- Re-ingesting the same JSON is a **no-op**.
- A partial ingest (process killed mid-way) can be **re-run** to fill in
  the rest.
- Two callers writing the same file at the same time is **safe**.

To **change** an existing row, the user must explicitly delete it first:

```python
(db.Experiment & "experiment_uuid='c1f1...'").delete()
db.ingest_json(...)
```

The library never silently overwrites — that's the safety rail against
accidental data loss.

## What gets inserted

```
Experiment (1)
├── Animal (N)
│   └── Preparation (N)
│       └── Cell (N)
│           └── EpochGroup (N)
│               └── EpochBlock (N)
│                   └── Epoch (N)
│                       ├── Response (N per device)
│                       ├── Stimulus (N per device)
│                       └── Background (N per device)
└── (Tag rows, if a tags JSON was provided)
```

`Protocol` rows are auto-created the first time a new `protocolID`
appears.

## Field-level mapping

The full mapping table — every JSON field → every DataJoint column —
is in [`spec/02_ingestion.md`](../spec/02_ingestion.md#field-level-mapping).

## Troubleshooting

- **`Duplicate entry '...' for key 'PRIMARY'`** — should not happen
  with default options. Caller passed `skip_existing=False`; the row
  already exists. Either let `skip_existing=True` (default), or delete
  first.
- **`Animal without uuid; skipped`** in the report — the source JSON
  has an entity missing its `uuid` field. This is a parse_data.py bug
  upstream — file an issue against the Symphony repo with the JSON
  attached.
- **`KeyError: 'protocol_id'`** — the EpochBlock has no `protocolID`.
  Inspect the JSON manually (`jq '.animals[0].preparations[0].cells[0].epoch_groups[0].epoch_blocks[0]'`).
- **Slow ingest of large files** — the bottleneck is per-row
  `insert1`. We deliberately don't bulk-batch because partial-failure
  recovery is easier with one row at a time. For one-off bulk loads of
  hundreds of files in parallel, `xargs -n1 -P8 python scripts/02_ingest_json.py`
  is the practical workaround.
