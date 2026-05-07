# Migration from the legacy code (`old/`)

The legacy code in `old/` (Flask app + helpers) is the pre-rewrite
state. This doc describes what changed and how to move data forward.

## What's different

| Legacy | New | Why |
|---|---|---|
| Flask REST app at `app.py` | Python library + CLI (`python -m symphony_dj`) | [ADR-0005](../spec/decisions/0005-drop-flask-rest.md) |
| Hard-coded `host='127.0.0.1'`, `password='simple'` in `schema.py` and `app.py` | `config/datajoint_config.yaml` + env vars | [ADR-0003](../spec/decisions/0003-yaml-configuration.md) |
| `id: int auto_increment` + `h5_uuid: varchar(255)` on every entity | UUID is the primary key | [ADR-0001](../spec/decisions/0001-uuid-primary-keys.md) |
| `properties: json` columns | `properties: json` (kept — DataJoint 2.0 has first-class JSON support; the legacy schema had this right) | [ADR-0002](../spec/decisions/0002-datajoint-v20-migration.md) |
| `helpers/utils.py` `NAS_DATA_DIR = '/Volumes/data/...'` | `paths.mea_data_root` in YAML / `$DJ_MEA_DATA_ROOT` | [ADR-0003](../spec/decisions/0003-yaml-configuration.md) |
| No `Background` table | First-class `Background` table | DJ JSON exposes per-device backgrounds, legacy dropped them. |
| `Tags.tag` was a comma-separated string | One `Tag` row per `(entity, user, tag)` | Native filtering; no string parsing in queries. |
| `MM/DD/YYYY HH:MM:SS:ffffff` strings parsed at query time | `datetime(6)` columns + `*_offset_hours` | Faster queries; correct DST. |
| Manual `dj.U().aggr(table, max=...)` | Not needed with UUID PKs | UUIDs come from upstream. |

## Re-ingesting an existing legacy database

The recommended path is **re-ingestion from the source JSON files** —
the H5 → JSON pipeline is the source of truth, and re-running it
produces deterministic UUIDs.

```bash
# 1. Stand up the new MySQL.
cd config && docker compose up -d
./../scripts/wait_for_mysql.sh

# 2. Initialize the new schema.
python -m symphony_dj init

# 3. Ingest the JSON corpus.
python -m symphony_dj ingest /Volumes/data/data/json/
```

Why this is preferred over a row-by-row migration:

- The JSON has every field the old DB had, plus `Background`.
- UUIDs survive — saved queries written against UUIDs (not the legacy
  `id` columns) keep working.
- No legacy-DB-specific bugs migrate forward.

## What you keep from the old code

`old/` is read-only reference. Concretely:

- `old/helpers/init.py` — Docker-bringup logic. Replaced by
  `config/docker-compose.yaml` (cleaner, no `subprocess.run`).
- `old/helpers/pop.py` — JSON ingestion. Replaced by
  `symphony_dj/ingest.py` (UUID-keyed, idempotent).
- `old/helpers/query.py` — query helpers. Replaced by
  `symphony_dj/query.py` (slimmer; the saved-query JSON format is
  preserved).
- `old/helpers/utils.py` — field maps and NAS paths. Field maps are no
  longer needed (UUIDs make the mapping direct); NAS paths moved to
  YAML.
- `old/app.py` / `old/app_refactored.py` — Flask app. Retired.

If a function from `old/` is still useful, port it into
`symphony_dj/` rather than referring back. Don't `from old.helpers ...`
from new code — the old package is not on the import path and that's
intentional.

## Removing `old/` and `src/python/api/`

Both directories are safe to delete once you're satisfied the new
package covers your needs. `src/python/api/schema.py` raises on import
to make this explicit. Run:

```bash
rm -rf old src/python/api
```

(Make sure nothing on your machine still does `from api.schema import ...`
or `from helpers.pop import ...` first — `git grep -E "from (api|helpers)"`)
