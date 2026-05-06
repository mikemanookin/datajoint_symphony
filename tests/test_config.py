"""Unit tests for ``symphony_dj.config`` — YAML loading, env-var overrides."""
from __future__ import annotations

from pathlib import Path

import pytest

from symphony_dj import load_config
from symphony_dj.config import (
    AppConfig,
    ConfigError,
    DatabaseConfig,
    IngestionConfig,
    PathsConfig,
)


def test_defaults_when_no_file(monkeypatch, tmp_path):
    monkeypatch.setenv("DJ_SYMPHONY_CONFIG", str(tmp_path / "nonexistent.yaml"))
    # Suppress the home-dir search by pointing HOME at an empty tmp dir.
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = load_config()
    assert isinstance(cfg, AppConfig)
    assert cfg.database.host == "127.0.0.1"
    assert cfg.schema_name == "symphony"
    assert cfg.ingestion.skip_existing is True


def test_explicit_path_wins(tmp_config_yaml, monkeypatch):
    p = tmp_config_yaml({
        "database": {"host": "example.com", "user": "alice", "password": "x"},
        "schema": {"name": "my_schema"},
    })
    cfg = load_config(str(p))
    assert cfg.database.host == "example.com"
    assert cfg.database.user == "alice"
    assert cfg.schema_name == "my_schema"
    assert cfg.source_path == p


def test_env_vars_override_yaml(tmp_config_yaml, monkeypatch):
    p = tmp_config_yaml({"database": {"host": "yaml.example.com"}})
    monkeypatch.setenv("DJ_HOST", "env.example.com")
    monkeypatch.setenv("DJ_PASSWORD", "from-env")
    monkeypatch.setenv("DJ_SCHEMA", "env_schema")
    cfg = load_config(str(p))
    assert cfg.database.host == "env.example.com"
    assert cfg.database.password == "from-env"
    assert cfg.schema_name == "env_schema"


def test_dj_symphony_config_env(tmp_config_yaml, monkeypatch):
    p = tmp_config_yaml({"database": {"host": "via-env-config.example.com"}})
    monkeypatch.setenv("DJ_SYMPHONY_CONFIG", str(p))
    cfg = load_config()
    assert cfg.database.host == "via-env-config.example.com"


def test_missing_paths_section_falls_back_to_defaults(tmp_config_yaml):
    p = tmp_config_yaml({"database": {"host": "h"}})
    cfg = load_config(str(p))
    assert cfg.paths.json_root is None
    assert cfg.paths.download_dir == Path.home() / "datajoint_downloads"


def test_invalid_yaml_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("- this\n   - is not\n  a mapping\n")
    with pytest.raises(ConfigError):
        load_config(str(bad))


def test_paths_expand_user(tmp_config_yaml, monkeypatch):
    monkeypatch.setenv("HOME", "/tmp/fakehome")
    p = tmp_config_yaml({"paths": {"json_root": "~/data/json"}})
    cfg = load_config(str(p))
    assert str(cfg.paths.json_root) == "/tmp/fakehome/data/json"


def test_dataclasses_frozen():
    cfg = AppConfig(
        database=DatabaseConfig(),
        schema_name="x",
        paths=PathsConfig(),
        ingestion=IngestionConfig(),
    )
    with pytest.raises(Exception):
        cfg.schema_name = "y"  # type: ignore[misc]
