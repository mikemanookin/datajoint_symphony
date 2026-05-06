"""YAML + env-var configuration loader.

See spec/03_configuration.md for the full schema. The loader returns a
frozen ``AppConfig``; mutate via ``dataclasses.replace`` if you need a
variant.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


# ---------------------------------------------------------------------------
# dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DatabaseConfig:
    host: str = "127.0.0.1"
    user: str = "root"
    password: str = ""
    port: int = 3306
    reconnect: bool = True
    use_tls: Optional[Dict[str, str]] = None


@dataclass(frozen=True)
class PathsConfig:
    json_root: Optional[Path] = None
    h5_root: Optional[Path] = None
    mea_data_root: Optional[Path] = None
    mea_analysis_root: Optional[Path] = None
    download_dir: Path = field(
        default_factory=lambda: Path.home() / "datajoint_downloads"
    )


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
    source_path: Optional[Path] = None  # the YAML file actually loaded


class ConfigError(RuntimeError):
    """Raised when a config file is present but malformed."""


# ---------------------------------------------------------------------------
# search & load
# ---------------------------------------------------------------------------


_REPO_DEFAULT = Path(__file__).resolve().parents[3] / "config" / "datajoint_config.yaml"


def _candidate_paths(explicit: Optional[str]) -> list[Path]:
    if explicit:
        return [Path(explicit).expanduser()]
    out: list[Path] = []
    env = os.environ.get("DJ_SYMPHONY_CONFIG")
    if env:
        out.append(Path(env).expanduser())
    out.append(Path.home() / ".datajoint_config.yaml")
    out.append(_REPO_DEFAULT)
    return out


def _read_yaml(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(
            f"{path} must contain a mapping at top level, got {type(data).__name__}"
        )
    return data


def _coerce_path(value: Any) -> Optional[Path]:
    if value in (None, "", False):
        return None
    return Path(str(value)).expanduser()


def _build_database(d: Dict[str, Any]) -> DatabaseConfig:
    base = DatabaseConfig()
    return replace(
        base,
        host=str(d.get("host", base.host)),
        user=str(d.get("user", base.user)),
        password=str(d.get("password", base.password) or ""),
        port=int(d.get("port", base.port)),
        reconnect=bool(d.get("reconnect", base.reconnect)),
        use_tls=d.get("use_tls", base.use_tls),
    )


def _build_paths(d: Dict[str, Any]) -> PathsConfig:
    base = PathsConfig()
    download_dir = d.get("download_dir")
    return PathsConfig(
        json_root=_coerce_path(d.get("json_root")),
        h5_root=_coerce_path(d.get("h5_root")),
        mea_data_root=_coerce_path(d.get("mea_data_root")),
        mea_analysis_root=_coerce_path(d.get("mea_analysis_root")),
        download_dir=(
            _coerce_path(download_dir) if download_dir not in (None, "")
            else base.download_dir
        ),
    )


def _build_ingestion(d: Dict[str, Any]) -> IngestionConfig:
    base = IngestionConfig()
    return replace(
        base,
        batch_size=int(d.get("batch_size", base.batch_size)),
        skip_existing=bool(d.get("skip_existing", base.skip_existing)),
        promote_unknown_protocols=bool(
            d.get("promote_unknown_protocols", base.promote_unknown_protocols)
        ),
    )


def _apply_env_overrides(cfg: AppConfig) -> AppConfig:
    env = os.environ
    db_kwargs: Dict[str, Any] = {}
    if "DJ_HOST" in env:
        db_kwargs["host"] = env["DJ_HOST"]
    if "DJ_USER" in env:
        db_kwargs["user"] = env["DJ_USER"]
    if "DJ_PASSWORD" in env:
        db_kwargs["password"] = env["DJ_PASSWORD"]
    if "DJ_PORT" in env:
        db_kwargs["port"] = int(env["DJ_PORT"])
    database = replace(cfg.database, **db_kwargs) if db_kwargs else cfg.database

    paths_kwargs: Dict[str, Any] = {}
    for env_name, attr in (
        ("DJ_JSON_ROOT", "json_root"),
        ("DJ_H5_ROOT", "h5_root"),
        ("DJ_MEA_DATA_ROOT", "mea_data_root"),
        ("DJ_MEA_ANALYSIS_ROOT", "mea_analysis_root"),
        ("DJ_DOWNLOAD_DIR", "download_dir"),
    ):
        if env_name in env:
            paths_kwargs[attr] = _coerce_path(env[env_name])
    paths = replace(cfg.paths, **paths_kwargs) if paths_kwargs else cfg.paths

    schema_name = env.get("DJ_SCHEMA", cfg.schema_name)

    return replace(
        cfg, database=database, paths=paths, schema_name=schema_name
    )


def load_config(path: Optional[str] = None) -> AppConfig:
    """Load an :class:`AppConfig` from YAML, applying env-var overrides.

    Resolution order (first existing file wins):

    1. ``path`` argument (explicit).
    2. ``$DJ_SYMPHONY_CONFIG``.
    3. ``~/.datajoint_config.yaml``.
    4. ``<repo>/config/datajoint_config.yaml``.

    If no file is found, returns an :class:`AppConfig` of pure defaults
    (with env-var overrides still applied).
    """
    chosen: Optional[Path] = None
    data: Dict[str, Any] = {}
    for candidate in _candidate_paths(path):
        if candidate.exists():
            data = _read_yaml(candidate)
            chosen = candidate
            break

    db_section = data.get("database") or {}
    schema_section = data.get("schema") or {}
    paths_section = data.get("paths") or {}
    ingestion_section = data.get("ingestion") or {}

    cfg = AppConfig(
        database=_build_database(db_section),
        schema_name=str(schema_section.get("name", "symphony")),
        paths=_build_paths(paths_section),
        ingestion=_build_ingestion(ingestion_section),
        source_path=chosen,
    )
    return _apply_env_overrides(cfg)


def write_example_config(path: str | Path) -> Path:
    """Write a fully commented example YAML to *path*. Useful for setup."""
    text = (
        Path(__file__).resolve().parents[3]
        / "config"
        / "datajoint_config.yaml"
    ).read_text()
    out = Path(path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    return out
