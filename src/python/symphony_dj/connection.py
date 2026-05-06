"""Connection + Database handle.

This module is the user-facing entry point for the package. It replaces
the legacy ``old/app.py`` Flask app — there's no HTTP surface, just a
Python class that wraps a configured DataJoint connection and exposes
every table plus ingestion / query helpers.

Typical use::

    from symphony_dj import connect

    db = connect()                                 # uses YAML / env-var config
    db.ingest_json("/path/to/exp_dj.json")
    db.Experiment.fetch()
    db.close()
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import datajoint as dj

from .config import AppConfig, load_config
from . import ingest as _ingest
from . import schema as _schema_module
from .query import Query

logger = logging.getLogger(__name__)


class Database:
    """Live handle to a Symphony DataJoint schema.

    Created by :func:`connect`. The class is intentionally light — every
    table class is exposed as an attribute (``db.Experiment``,
    ``db.Epoch``, ...) and the helpers (:meth:`ingest_json`,
    :attr:`query`, ...) delegate to the relevant module.
    """

    def __init__(self, config: AppConfig, schema: dj.Schema, tables: dict):
        self.config = config
        self.schema = schema
        self._tables = tables
        # Expose each table class as an attribute on this object.
        for name, cls in tables.items():
            setattr(self, name, cls)
        self._query: Optional[Query] = None

    # -- ingestion ------------------------------------------------------

    def ingest_json(
        self,
        json_path: str | Path,
        *,
        h5_path: Optional[str | Path] = None,
        tags_path: Optional[str | Path] = None,
        skip_existing: Optional[bool] = None,
    ) -> _ingest.IngestReport:
        """Ingest a single ``*_dj.json`` file. See spec/02_ingestion.md."""
        skip = (
            self.config.ingestion.skip_existing
            if skip_existing is None else skip_existing
        )
        return _ingest.ingest_json(
            self,
            json_path,
            h5_path=h5_path,
            tags_path=tags_path,
            skip_existing=skip,
        )

    def ingest_directory(
        self,
        root: str | Path,
        *,
        pattern: str = "*_dj.json",
        skip_existing: Optional[bool] = None,
    ) -> _ingest.IngestReport:
        """Recursively ingest every ``*_dj.json`` under ``root``."""
        skip = (
            self.config.ingestion.skip_existing
            if skip_existing is None else skip_existing
        )
        return _ingest.ingest_directory(
            self, root, pattern=pattern, skip_existing=skip
        )

    # -- querying -------------------------------------------------------

    @property
    def query(self) -> Query:
        if self._query is None:
            self._query = Query(self)
        return self._query

    # -- diagnostics / lifecycle ---------------------------------------

    def is_connected(self) -> bool:
        try:
            return bool(dj.conn().is_connected)
        except Exception:
            return False

    def diagram(self):
        """Return a ``dj.Diagram`` for this schema (for Jupyter rendering)."""
        return dj.Diagram(self.schema)

    def drop(self, force: bool = False) -> None:
        """Drop the entire schema (DESTRUCTIVE; tests use this)."""
        if force:
            self.schema.drop_quick()
        else:
            self.schema.drop()

    def close(self) -> None:
        """Close the underlying DataJoint connection."""
        try:
            if dj.conn().is_connected:
                dj.conn().close()
        except Exception:
            logger.exception("Error closing DataJoint connection")

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()
        return False

    def __repr__(self) -> str:
        host = self.config.database.host
        return f"<symphony_dj.Database schema={self.schema.database!r} host={host!r}>"


# ---------------------------------------------------------------------------
# Connect entry point
# ---------------------------------------------------------------------------


def _apply_dj_config(cfg: AppConfig) -> None:
    """Populate ``dj.config`` from an :class:`AppConfig`."""
    dj.config["database.host"] = cfg.database.host
    dj.config["database.user"] = cfg.database.user
    dj.config["database.password"] = cfg.database.password
    dj.config["database.port"] = cfg.database.port
    dj.config["database.reconnect"] = cfg.database.reconnect
    if cfg.database.use_tls is not None:
        dj.config["database.use_tls"] = cfg.database.use_tls
    if cfg.paths.download_dir is not None:
        dj.config["safemode"] = True
        dj.config["loglevel"] = "INFO"


def connect(
    config: Optional[AppConfig] = None,
    *,
    create_schema: bool = True,
) -> Database:
    """Open a DataJoint connection and declare the Symphony schema.

    Parameters
    ----------
    config:
        :class:`AppConfig` to use. If ``None``, calls :func:`load_config`.
    create_schema:
        If True (default), declares the schema if missing. If False, the
        caller is responsible — useful in tests that already manage the
        schema lifecycle.

    Returns
    -------
    :class:`Database`
    """
    if config is None:
        config = load_config()

    _apply_dj_config(config)
    conn = dj.conn(reset=True)  # ensure config is picked up
    if not conn.is_connected:
        conn.connect()
    logger.info(
        "Connected to %s as %s; schema=%s",
        config.database.host,
        config.database.user,
        config.schema_name,
    )

    schema = dj.Schema(config.schema_name, create_schema=create_schema)
    tables = _schema_module.declare(schema)
    return Database(config, schema, tables)
