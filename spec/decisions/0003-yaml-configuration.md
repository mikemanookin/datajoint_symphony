# ADR 0003 — YAML configuration with env-var overrides

**Status:** Accepted
**Date:** 2026-05-06

## Context

The legacy `app.py` and `schema.py` both hard-coded `database.host =
'127.0.0.1'`, `database.user = 'root'`, `database.password = 'simple'`
at module-import time. NAS paths lived in `helpers/utils.py` as
`NAS_DATA_DIR = '/Volumes/data/data/sorted'`. This made the code:

- **Unsharable** — anyone with a different DB or different mount point
  had to edit Python files.
- **Insecure** — a real password committed to the repo, even as a
  default, is a bad pattern.
- **CI-hostile** — no clean way to point tests at a Docker MySQL on a
  random port.

## Decision

A single `datajoint_config.yaml` file declares all environment-specific
values. Environment variables override individual fields at runtime.
The library never hard-codes a host, user, password, or NAS path.

Search order:
1. Explicit `path` argument to `load_config(path)`.
2. `$DJ_SYMPHONY_CONFIG`.
3. `~/.datajoint_config.yaml`.
4. `<repo>/config/datajoint_config.yaml` (repo default for dev).
5. Built-in defaults (used only if all secrets come from env vars).

Override env vars: `DJ_HOST`, `DJ_USER`, `DJ_PASSWORD`, `DJ_PORT`,
`DJ_SCHEMA`, `DJ_JSON_ROOT`, `DJ_H5_ROOT`, `DJ_MEA_DATA_ROOT`,
`DJ_MEA_ANALYSIS_ROOT`, `DJ_DOWNLOAD_DIR`.

Full schema in [`03_configuration.md`](../03_configuration.md).

## Consequences

**Good**

- Zero edits to Python to point at a different DB.
- CI can drive everything via env vars; no secrets in repo.
- The `config/datajoint_config.yaml` shipped in the repo *is* the
  Docker-default fixture, which is also what `tests/conftest.py` uses —
  one config drives both dev and CI.

**Cost**

- One more file to read to understand startup. We mitigate with a
  `connect()` log line that prints the source path of the loaded
  config.
- YAML's `null` vs missing-key distinction has tripped people up. The
  loader documents that omitted keys fall back to defaults; explicit
  `null` is treated the same.

## Alternatives considered

- **`.env` with `python-dotenv`.** Works, but stringly-typed everything.
  YAML lets us keep nested structure (`database.use_tls.ca`).
- **Read directly from `dj.config`.** DataJoint's own config supports
  loading from `dj_local_conf.json`. We considered piggybacking, but it
  doesn't cover NAS paths or our ingestion knobs, so we'd still need a
  second file. One file is better.
