"""pytest fixtures for the symphony_dj test suite.

The integration fixtures depend on a reachable MySQL (the
``config/docker-compose.yaml`` Compose service is the canonical source).
If MySQL is not reachable, dependent tests are auto-skipped via the
``mysql_available`` fixture. Pure unit tests (``test_config``,
``test_timestamps``, ``test_schema``, ``test_ingest_unit``) don't touch
this fixture and run anywhere.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Iterator

import pytest

# Make ``src/python`` importable when running pytest from the repo root
# without an editable install.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "python"))


FIXTURE_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Pure-data fixtures (no DB)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def sample_json_path() -> Path:
    return FIXTURE_DIR / "sample_dj.json"


@pytest.fixture(scope="session")
def sample_tags_path() -> Path:
    return FIXTURE_DIR / "sample_tags.json"


@pytest.fixture(scope="session")
def sample_json(sample_json_path) -> dict:
    with sample_json_path.open("r") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# AppConfig fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_config_yaml(tmp_path) -> Path:
    """Return a callable that writes a YAML file from a dict and returns the path."""
    def _write(data: dict, name: str = "datajoint_config.yaml") -> Path:
        import yaml
        p = tmp_path / name
        p.write_text(yaml.safe_dump(data))
        return p
    return _write


@pytest.fixture(scope="session")
def app_config():
    """An :class:`AppConfig` honouring the env vars or defaults."""
    from symphony_dj import load_config
    return load_config()


# ---------------------------------------------------------------------------
# DB fixtures (skip if MySQL unreachable)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def mysql_available(app_config) -> bool:
    """True if a DataJoint connection succeeds against ``app_config``."""
    import datajoint as dj
    dj.config["database.host"] = app_config.database.host
    dj.config["database.user"] = app_config.database.user
    dj.config["database.password"] = app_config.database.password
    dj.config["database.port"] = app_config.database.port
    try:
        dj.conn(reset=True).connect()
        return bool(dj.conn().is_connected)
    except Exception:
        return False


@pytest.fixture
def db(app_config, mysql_available) -> Iterator:
    """Fresh schema for each test, dropped at teardown."""
    if not mysql_available:
        pytest.skip("MySQL unavailable; integration test skipped")

    from dataclasses import replace
    from symphony_dj import connect

    # Random schema name so tests don't collide with the user's real schema.
    suffix = uuid.uuid4().hex[:8]
    test_cfg = replace(app_config, schema_name=f"test_symphony_{suffix}")
    database = connect(test_cfg)
    try:
        yield database
    finally:
        try:
            database.drop(force=True)
        finally:
            database.close()


def pytest_collection_modifyitems(config, items):  # noqa: D401
    """Mark tests in ``test_ingest_integration``, ``test_query``, and
    ``test_invariants`` as ``integration`` so callers can filter."""
    for item in items:
        path = str(item.fspath)
        if any(s in path for s in ("integration", "test_query", "test_invariants")):
            item.add_marker(pytest.mark.integration)
