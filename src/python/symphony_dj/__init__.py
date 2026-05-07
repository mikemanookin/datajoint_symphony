"""symphony_dj — DataJoint 2.0 ingestion + query for Symphony 3 metadata.

Public surface:

    from symphony_dj import connect, load_config

    cfg = load_config()           # see config.py
    db  = connect(cfg)            # opens MySQL, declares schema, returns Database

    db.ingest_json("/path/to/exp_dj.json")
    db.Experiment.to_dicts()
    db.query.tree(experiment_uuid)
    db.close()

The package targets DataJoint 2.0. Spec lives in ./spec/ at the repo root.
"""

from .config import (
    AppConfig,
    DatabaseConfig,
    PathsConfig,
    IngestionConfig,
    ConfigError,
    load_config,
)
from .connection import Database, connect
from . import schema
from . import timestamps

__all__ = [
    "AppConfig",
    "DatabaseConfig",
    "PathsConfig",
    "IngestionConfig",
    "ConfigError",
    "Database",
    "connect",
    "load_config",
    "schema",
    "timestamps",
]

__version__ = "2.0.0"
