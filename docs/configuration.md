# Configuration

Every environment-specific value (DB host, password, NAS paths) is
loaded from a YAML file or environment variables. The library never
hard-codes a host or credential.

For the formal spec, see [`spec/03_configuration.md`](../spec/03_configuration.md).
This doc is the practical "how do I set it up" walkthrough.

## File search order

`symphony_dj.config.load_config()` looks for the first existing file in
this order, then applies env-var overrides:

1. Path passed to `load_config(path)`.
2. `$DJ_SYMPHONY_CONFIG`.
3. `~/.datajoint_config.yaml`.
4. `<repo>/config/datajoint_config.yaml`.

## Minimal example

```yaml
# ~/.datajoint_config.yaml
database:
  host: mysql.lab.example.com
  user: mike
  password: see-1Password
schema:
  name: symphony_prod
paths:
  json_root: /Volumes/data/data/json
  h5_root:   /Volumes/data/data/h5
```

## All fields

```yaml
database:
  host: 127.0.0.1
  user: root
  password: simple
  port: 3306
  reconnect: true
  use_tls: null              # or { ca: ..., cert: ..., key: ... }

schema:
  name: symphony

paths:
  json_root: null            # /Volumes/data/data/json
  h5_root: null              # /Volumes/data/data/h5
  mea_data_root: null        # /Volumes/data/data/sorted
  mea_analysis_root: null    # /Volumes/data/analysis
  download_dir: ~/datajoint_downloads

ingestion:
  batch_size: 1000
  skip_existing: true
  promote_unknown_protocols: true
```

Every section is optional. Missing sections fall back to documented
defaults.

## Environment-variable overrides

These take priority over the file. Useful for CI, Docker, and shared
machines:

| Env var | Overrides |
|---|---|
| `DJ_HOST`               | `database.host` |
| `DJ_USER`               | `database.user` |
| `DJ_PASSWORD`           | `database.password` |
| `DJ_PORT`               | `database.port` |
| `DJ_SCHEMA`             | `schema.name` |
| `DJ_JSON_ROOT`          | `paths.json_root` |
| `DJ_H5_ROOT`            | `paths.h5_root` |
| `DJ_MEA_DATA_ROOT`      | `paths.mea_data_root` |
| `DJ_MEA_ANALYSIS_ROOT`  | `paths.mea_analysis_root` |
| `DJ_DOWNLOAD_DIR`       | `paths.download_dir` |
| `DJ_SYMPHONY_CONFIG`    | path to the YAML itself |

## Inspecting the resolved config

```bash
python -m symphony_dj config
```

Prints the host/user/schema and which file the values came from. The
password is replaced with asterisks.

## Security tips

- Don't commit a `~/.datajoint_config.yaml` containing real
  credentials. The repo's `config/datajoint_config.yaml` is the dev /
  Docker fixture only.
- For shared machines: `chmod 600 ~/.datajoint_config.yaml`.
- For CI: prefer `DJ_PASSWORD` over committing a config file.
