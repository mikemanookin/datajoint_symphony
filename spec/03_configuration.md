# Configuration Specification

**Status:** Stable
**File:** `datajoint_config.yaml`
**Default search order:** `$DJ_SYMPHONY_CONFIG` → `~/.datajoint_config.yaml` → `<repo>/config/datajoint_config.yaml`

The library has no hard-coded host, credentials, or NAS path. Every
environment-specific value comes from YAML, with environment variables
as a runtime override (handy for CI and Docker).

## File schema

```yaml
database:
  host: 127.0.0.1                 # MySQL host
  user: root                      # MySQL user
  password: simple                # MySQL password (omit and use $DJ_PASSWORD instead)
  port: 3306                      # MySQL port
  reconnect: true                 # auto-reconnect on dropped connections
  use_tls: null                   # null | false | { ca: ..., cert: ..., key: ... }

schema:
  name: symphony                  # MySQL schema name to create / connect to

paths:
  json_root: /Volumes/data/data/json          # where _dj.json files live
  h5_root: /Volumes/data/data/h5              # where source .h5 files live
  mea_data_root: /Volumes/data/data/sorted    # spike-sorting outputs (optional)
  mea_analysis_root: /Volumes/data/analysis   # cell typing outputs (optional)
  download_dir: ~/datajoint_downloads         # where query results land

ingestion:
  batch_size: 1000                # rows per insert call
  skip_existing: true             # if false, raises on duplicate PK
  promote_unknown_protocols: true # auto-insert new Protocol rows
```

All sections are optional. A YAML missing a section falls back to the
defaults listed above.

## Loading semantics

`symphony_dj.config.load_config(path: Optional[str] = None) -> AppConfig`

1. **Explicit path** — if `path` is passed, only that file is read.
2. **Env var** — if `DJ_SYMPHONY_CONFIG` is set, only that file is read.
3. **User home** — if `~/.datajoint_config.yaml` exists, it is read.
4. **Repo default** — `<repo>/config/datajoint_config.yaml` is read if
   the user is running from a checkout (file presence is the trigger).
5. **Built-in defaults** — if no file is found, the loader returns
   defaults; this only works if env vars supply credentials.

After the YAML is loaded, the following **env vars override** their
YAML counterparts (use these in CI / Docker):

| Env var | Overrides |
|---|---|
| `DJ_HOST` | `database.host` |
| `DJ_USER` | `database.user` |
| `DJ_PASSWORD` | `database.password` |
| `DJ_PORT` | `database.port` |
| `DJ_SCHEMA` | `schema.name` |
| `DJ_JSON_ROOT` | `paths.json_root` |
| `DJ_H5_ROOT` | `paths.h5_root` |
| `DJ_MEA_DATA_ROOT` | `paths.mea_data_root` |
| `DJ_MEA_ANALYSIS_ROOT` | `paths.mea_analysis_root` |
| `DJ_DOWNLOAD_DIR` | `paths.download_dir` |

## Returned object

```python
@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    user: str
    password: str
    port: int = 3306
    reconnect: bool = True
    use_tls: Optional[Dict[str, str]] = None

@dataclass(frozen=True)
class PathsConfig:
    json_root: Optional[Path] = None
    h5_root: Optional[Path] = None
    mea_data_root: Optional[Path] = None
    mea_analysis_root: Optional[Path] = None
    download_dir: Path = Path.home() / "datajoint_downloads"

@dataclass(frozen=True)
class IngestionConfig:
    batch_size: int = 1000
    skip_existing: bool = True
    promote_unknown_protocols: bool = True

@dataclass(frozen=True)
class AppConfig:
    database: DatabaseConfig
    schema_name: str
    paths: PathsConfig
    ingestion: IngestionConfig
    source_path: Optional[Path]   # the YAML file actually loaded, for debugging
```

`AppConfig` is frozen — mutate by `dataclasses.replace`, never in
place. This guarantees a connected `Database` handle reflects the
config it was built from.

## Security

- Don't commit a `datajoint_config.yaml` containing real passwords.
  The file at `config/datajoint_config.yaml` is shipped with the
  Docker default (`root` / `simple` against `127.0.0.1:3306`) — that's
  the dev fixture only.
- For shared machines, put the real config at
  `~/.datajoint_config.yaml` with mode `0600`. The loader does not
  read mode but the docs ([`docs/configuration.md`](../docs/configuration.md))
  remind users.
- `DJ_PASSWORD` is preferred for CI / Docker / shared boxes — it
  doesn't leave a file behind.

## Connection lifecycle

```python
from symphony_dj import connect, load_config

cfg = load_config()                  # reads YAML + env, returns AppConfig
db  = connect(cfg)                   # opens dj.conn() and instantiates the schema
# ... use db.Experiment, db.ingest_json, etc. ...
db.close()                           # closes dj.conn()
```

`connect()` is a thin wrapper that:

1. Calls `dj.config.update({"database.host": cfg.database.host, ...})`.
2. Calls `dj.conn().connect()`.
3. Builds a `dj.Schema(cfg.schema_name)` decorator.
4. Declares every table in `symphony_dj.schema` against that schema.
5. Returns a `Database` namespace object exposing each table class plus
   `ingest_json`, `ingest_directory`, and `query` helpers.

Re-calling `connect()` with the same `AppConfig` is idempotent and
returns a fresh handle; existing handles are unaffected.

## What the legacy app did differently

The legacy `app.py` declared `dj.config['database.host'] = '127.0.0.1'`
at module import time, hard-coded `root`/`simple`, and parsed
`/Volumes/data/...` paths in `helpers/utils.py`. The config object here
replaces all of that. See [ADR-0003](decisions/0003-yaml-configuration.md).
