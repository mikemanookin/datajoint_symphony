# Query API Specification

**Status:** Stable
**Module:** `symphony_dj.query`
**Audience:** library users (Python scripts, Jupyter notebooks)

This spec describes the **public** Python interface for reading from a
populated DataJoint schema. Direct DataJoint expressions
(`db.Epoch & {...}`.fetch()) are always available; the helpers here are
for the patterns the team hits over and over.

## Surface

```python
from symphony_dj import connect

db = connect()

# Native DataJoint queries — always available:
db.Experiment & "lab='Manookin'"
(db.Epoch * db.EpochBlock & {"protocol_id": "manookinlab.protocols.SpatialNoise"})

# Convenience helpers:
db.query.tree(experiment_uuid)              # nested dict view of an experiment
db.query.epochs_for(protocol_id="...")      # filtered Epoch dataset (joined to block/group)
db.query.responses(epoch_uuid)              # iterate Response rows for an Epoch
db.query.read_response_data(epoch_uuid, device="Amp1")
                                            # raw samples from the .h5 (uses h5io)
db.query.fields(table_name)                 # introspect columns + types
db.query.levels()                           # ordered list of hierarchy table names
db.query.save("name", expression)           # persist a query expression (JSON form)
db.query.load("name")                       # reload a saved query expression
db.query.delete("name")                     # remove a saved query
```

## Hierarchy traversal

`db.query.tree(experiment_uuid)` returns a nested dict mirroring the DJ
JSON shape:

```python
{
  "experiment_uuid": "...",
  "label": "20260410H",
  "animals": [
    {
      "animal_uuid": "...",
      "label": "A1",
      "preparations": [
        {
          "preparation_uuid": "...",
          "label": "OD",
          "cells": [
            {
              "cell_uuid": "...",
              "label": "cell1",
              "epoch_groups": [...],   # ... etc.
            }
          ]
        }
      ]
    }
  ]
}
```

The depth is configurable: `tree(uuid, depth="cell")` stops at the
Cell level, useful for big experiments where the full depth is too
much.

## Filtered datasets

Every helper returns a **DataJoint expression**, not a fetched
DataFrame. That keeps queries composable:

```python
sn_epochs = db.query.epochs_for(protocol_id="manookinlab.protocols.SpatialNoise")
da_epochs = sn_epochs & "rig='B'"             # further restrict
df = (da_epochs * db.Cell).fetch(format="frame")
```

`epochs_for(...)` joins `Epoch * EpochBlock * EpochGroup * Cell *
Preparation * Animal * Experiment` and filters on whichever kwargs the
caller passes (column-name-matched at any level).

## Raw sample access

`db.query.read_response_data(epoch_uuid, device)` opens the matching
`.h5` (resolved via `Experiment.h5_path` or the configured `h5_root` +
the experiment label) and returns a numpy array of measurements:

```python
samples = db.query.read_response_data("c1f1...", device="Amp1")
# samples.shape == (n_samples,)
# samples.dtype == float64
```

Sample arrays are not cached in memory; each call is one open + read.
For batch access use `db.h5io.open(experiment_uuid)` directly.

## Saved queries

A saved query is a dict serialization of a DataJoint expression tree:

```python
{
  "and": [
    {"cond": {"table": "EpochBlock", "expr": "protocol_id LIKE 'manookinlab%'"}},
    {"cond": {"table": "Cell", "expr": "cell_type='ParasolOff'"}}
  ]
}
```

The library ships this format as JSON in `paths.download_dir/queries.json`.
This is the same format the legacy app used (see `old/helpers/query.py
:: apply_conditions`); we keep it because it's UI-friendly.

## Tags

```python
db.query.tags(epoch_uuid)                       # list[(user, tag)]
db.query.add_tag(epoch_uuid, user, tag)         # idempotent
db.query.remove_tag(epoch_uuid, user, tag)      # idempotent
db.query.export_tags(path)                      # write a tags JSON sidecar
db.query.import_tags(path)                      # read a tags JSON sidecar
```

Tags are **per-user**, **per-entity**. Removal of a `(user, tag)` pair
is the only way to delete; re-ingesting an experiment doesn't touch
tags.

## Field introspection

```python
db.query.levels()
# ['experiment','animal','preparation','cell',
#  'epoch_group','epoch_block','epoch','response','stimulus','background']

db.query.fields("epoch_block")
# [
#   ('epoch_block_uuid', 'string'),
#   ('epoch_group_uuid', 'string'),
#   ('protocol_id',      'string'),
#   ('data_file',        'string'),
#   ('start_time',       'date'),
#   ('parameters',       'json'),
#   ('properties',       'json'),
#   ...
# ]
```

`fields()` is what lets a downstream UI render dynamic filter widgets
without hard-coding column lists. The legacy `app.py /query/get-table-
fields` endpoint is the inspiration; the Python form is the canonical
one and any future REST surface re-exposes it.

## Notebook idioms

The spec assumes Jupyter usage. Standard pattern:

```python
import datajoint as dj
from symphony_dj import connect
db = connect()

dj.Diagram(db.schema)                                     # render ER diagram
(db.Experiment * db.Animal).fetch(format="frame")         # → pandas DataFrame
```

`scripts/04_query_jupyter.ipynb` ships a worked example.

## Stability

The helpers in this spec are stable; native DataJoint expressions
against the table classes are also stable as long as
[`01_schema.md`](01_schema.md) hasn't changed. Internal helpers (private
methods on `_Query`) are not part of the contract.
