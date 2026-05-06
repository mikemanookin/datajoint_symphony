# Query Guide

Reading from the schema, from Python or Jupyter. The formal interface
spec is in [`spec/04_query_api.md`](../spec/04_query_api.md).

## Native DataJoint expressions

Every table is exposed as an attribute on the `Database` handle, and
behaves as a normal `dj.Manual` subclass:

```python
from symphony_dj import connect

db = connect()

# Restrict
recent = db.Experiment & "start_time > '2026-01-01'"

# Project
labels = (db.Cell & "cell_type='ParasolOff'").proj("label", "preparation_uuid")

# Join
sn = db.Epoch * db.EpochBlock & {"protocol_id": "manookinlab.protocols.SpatialNoise"}

# Fetch
df = sn.fetch(format="frame")
rows = sn.fetch(as_dict=True)
```

This is the primary interface. Use it for anything ad hoc.

## Helper API

`db.query` is a thin layer for the common patterns:

### Hierarchy navigation

```python
uuid = db.Experiment.fetch1("experiment_uuid")
tree = db.query.tree(uuid, depth="cell")
# {'experiment_uuid': '...', 'animals': [{'animal_uuid': '...', 'preparations': [...]}]}
```

`depth` accepts any of `experiment`, `animal`, `preparation`, `cell`,
`epoch_group`, `epoch_block`, `epoch`. Default is `epoch` (skips
per-device rows for performance).

### Filtered datasets

```python
sn_epochs = db.query.epochs_for(protocol_id="manookinlab.protocols.SpatialNoise")
sn_cells  = db.query.epochs_for(rig="MEA Rig B")
```

`epochs_for(...)` joins `Epoch * EpochBlock * EpochGroup * Cell *
Preparation * Animal * Experiment` and applies the keyword filters at
whichever level matches.

### Per-epoch device rows

```python
db.query.responses(epoch_uuid)
db.query.stimuli(epoch_uuid)
db.query.backgrounds(epoch_uuid)
```

### Saved queries

```python
db.query.save("my_filter", {"and": [{"cond": ...}, ...]})
saved = db.query.load("my_filter")
db.query.delete_saved("my_filter")
```

The persisted location is `paths.download_dir/queries.json`.

### Tags

```python
db.query.add_tag("Epoch", epoch_uuid, user="mike", tag="good")
db.query.tags(epoch_uuid)                      # [(user, tag), ...]
db.query.remove_tag(epoch_uuid, "mike", "bad")
```

### Field introspection

```python
db.query.levels()
# ['experiment','animal','preparation','cell','epoch_group','epoch_block','epoch','response','stimulus','background']

db.query.fields("epoch_block")
# [('epoch_block_uuid', 'string'), ('epoch_group_uuid','string'), ('protocol_id','string'), ...]
```

## Raw sample reads

`Response` / `Stimulus` rows store metadata; samples live in the source
HDF5. To read:

```python
from symphony_dj import h5io

row = (db.Response * db.Experiment).fetch(
    "h5_path", "epoch_uuid", "device_name", "h5path",
    limit=1, as_dict=True,
)[0]

samples = h5io.read_response_data(
    row["h5_path"],
    row["epoch_uuid"],
    row["device_name"],
    h5path_hint=row["h5path"],
)
```

`samples` is a 1-D `numpy.float64` array (units are stripped from
Symphony's compound `MEASUREMENT` dtype).

For batched access, use `h5io.open_experiment_file(h5_path)` directly
and reuse the file handle.

## Jupyter

[`scripts/04_query_jupyter.ipynb`](../scripts/04_query_jupyter.ipynb)
is a worked example: connect, render diagram, run native + helper
queries, fetch raw samples.

## Limitations

- `db.query.tree()` runs one fetch per level, depth-first. For experiments
  with thousands of epochs this is fine; for full-database tree dumps,
  prefer the joined-fetch approach (`(db.Experiment * db.Animal * db.Preparation * ...).fetch(format="frame")`)
  and reshape in pandas.
- Saved queries are JSON-only — no Python lambdas. The serialized form
  is intentionally limited to what a UI could render.
