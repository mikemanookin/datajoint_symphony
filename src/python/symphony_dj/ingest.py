"""DJ JSON → DataJoint ingestion.

Implements ``spec/02_ingestion.md`` — every Symphony entity from a
``*_dj.json`` document becomes a row in the corresponding DataJoint
table, keyed by the upstream UUID.

The public entry points are :func:`ingest_json` and
:func:`ingest_directory`. Both are idempotent.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from . import timestamps as ts

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


@dataclass
class IngestReport:
    """Summary of an ingest call. Returned from ``ingest_json`` /
    ``ingest_directory``. The numbers count rows *attempted* to insert;
    duplicates that were skipped via ``skip_duplicates=True`` still count
    here so the user sees what the JSON contained.
    """

    files: List[str] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def add(self, table: str, n: int = 1) -> None:
        self.counts[table] = self.counts.get(table, 0) + n

    def merge(self, other: "IngestReport") -> None:
        self.files.extend(other.files)
        for k, v in other.counts.items():
            self.counts[k] = self.counts.get(k, 0) + v
        self.errors.extend(other.errors)

    def __str__(self) -> str:
        lines = [f"Ingested {len(self.files)} file(s)."]
        for table in (
            "Experiment Animal Preparation Cell EpochGroup EpochBlock "
            "Epoch Response Stimulus Background Tag Protocol"
        ).split():
            n = self.counts.get(table, 0)
            if n:
                lines.append(f"  {table}: {n}")
        if self.errors:
            lines.append(f"Errors: {len(self.errors)}")
            for err in self.errors[:5]:
                lines.append(f"  - {err}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tuple builders — pure functions, no DB. Tested in tests/test_ingest_unit.py.
# ---------------------------------------------------------------------------


def _props(d: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Coerce a properties dict to a JSON-safe form (drop ``None``s only at
    the leaves so callers see exactly what the JSON had)."""
    return d if isinstance(d, dict) else {}


def _attrs(d: Dict[str, Any]) -> Dict[str, Any]:
    """Helper: pull the attributes sub-dict from a SourceObj-style dict.

    The DJ JSON encodes Source-derived entities (Animal, Preparation, ...)
    by serialising the parse_data.SourceObj dataclass directly, so the
    fields live at the top level (``label``, ``uuid``, ``properties``,
    ``attributes``, ``start_time``). Older legacy dumps put them under
    ``attributes``. Accept both.
    """
    return d.get("attributes") or d


def build_experiment_tuple(
    exp: Dict[str, Any],
    *,
    json_path: Optional[Path] = None,
    h5_path: Optional[Path] = None,
) -> Dict[str, Any]:
    a = _attrs(exp)
    start, start_off = ts.split_dotnet_pair(a, "startTime")
    end, end_off = ts.split_dotnet_pair(a, "endTime")
    if start is None:
        # parse_data emits a legacy-format string in `start_time`
        start = ts.parse_legacy_string(exp.get("start_time"))
    return {
        "experiment_uuid": exp.get("uuid") or a.get("uuid"),
        "purpose": a.get("purpose"),
        "start_time": start,
        "start_offset_hours": start_off,
        "end_time": end,
        "end_offset_hours": end_off,
        "keywords": _join_keywords(exp.get("keywords") or a.get("keywords")),
        "experimenter": exp.get("experimenter"),
        "institution": exp.get("institution"),
        "lab": exp.get("lab"),
        "project": exp.get("project"),
        "rig": exp.get("rig"),
        "rig_type": exp.get("rig_type"),
        "h5_path": str(h5_path) if h5_path else None,
        "json_path": str(json_path) if json_path else None,
        "properties": _props(exp.get("properties")),
    }


def build_animal_tuple(
    animal: Dict[str, Any], experiment_uuid: str
) -> Dict[str, Any]:
    a = _attrs(animal)
    start, start_off = ts.split_dotnet_pair(a, "creationTime")
    if start is None:
        start = ts.parse_legacy_string(animal.get("start_time"))
    props = _props(animal.get("properties"))
    return {
        "animal_uuid": animal.get("uuid") or a.get("uuid"),
        "experiment_uuid": experiment_uuid,
        "label": animal.get("label") or a.get("label"),
        "start_time": start,
        "start_offset_hours": start_off,
        "animal_id": animal.get("id") or props.get("id"),
        "description": animal.get("description") or props.get("description"),
        "sex": animal.get("sex") or props.get("sex"),
        "age": animal.get("age") or props.get("age"),
        "weight": animal.get("weight") or props.get("weight"),
        "dark_adaptation": (
            animal.get("darkAdaptation") or props.get("darkAdaptation")
        ),
        "species": animal.get("species") or props.get("species"),
        "properties": props,
    }


def build_preparation_tuple(
    prep: Dict[str, Any], animal_uuid: str
) -> Dict[str, Any]:
    a = _attrs(prep)
    start, start_off = ts.split_dotnet_pair(a, "creationTime")
    if start is None:
        start = ts.parse_legacy_string(prep.get("start_time"))
    props = _props(prep.get("properties"))
    return {
        "preparation_uuid": prep.get("uuid") or a.get("uuid"),
        "animal_uuid": animal_uuid,
        "label": prep.get("label") or a.get("label"),
        "start_time": start,
        "start_offset_hours": start_off,
        "bath_solution": prep.get("bathSolution") or props.get("bathSolution"),
        # NB: JSON key is singular `preparation` for the type
        "preparation_type": (
            prep.get("preparationType") or props.get("preparation")
        ),
        "region": prep.get("region") or props.get("region"),
        "array_pitch": prep.get("arrayPitch") or props.get("arrayPitch"),
        "properties": props,
    }


def build_cell_tuple(
    cell: Dict[str, Any], preparation_uuid: str
) -> Dict[str, Any]:
    a = _attrs(cell)
    start, start_off = ts.split_dotnet_pair(a, "creationTime")
    if start is None:
        start = ts.parse_legacy_string(cell.get("start_time"))
    props = _props(cell.get("properties"))
    return {
        "cell_uuid": cell.get("uuid") or a.get("uuid"),
        "preparation_uuid": preparation_uuid,
        "label": cell.get("label") or a.get("label"),
        "start_time": start,
        "start_offset_hours": start_off,
        "cell_type": cell.get("type") or props.get("type"),
        "properties": props,
    }


def build_epoch_group_tuple(
    eg: Dict[str, Any], cell_uuid: str
) -> Dict[str, Any]:
    a = _attrs(eg)
    start, start_off = ts.split_dotnet_pair(a, "startTime")
    end, end_off = ts.split_dotnet_pair(a, "endTime")
    if start is None:
        start = ts.parse_legacy_string(eg.get("start_time"))
    if end is None:
        end = ts.parse_legacy_string(eg.get("end_time"))
    return {
        "epoch_group_uuid": eg.get("uuid") or a.get("uuid"),
        "cell_uuid": cell_uuid,
        "label": eg.get("label") or a.get("label"),
        "start_time": start,
        "start_offset_hours": start_off,
        "end_time": end,
        "end_offset_hours": end_off,
        "keywords": _join_keywords(eg.get("keywords") or a.get("keywords")),
        "properties": _props(eg.get("properties")),
    }


def build_epoch_block_tuple(
    eb: Dict[str, Any], epoch_group_uuid: str
) -> Dict[str, Any]:
    a = _attrs(eb)
    start, start_off = ts.split_dotnet_pair(a, "startTime")
    end, end_off = ts.split_dotnet_pair(a, "endTime")
    if start is None:
        start = ts.parse_legacy_string(eb.get("start_time"))
    if end is None:
        end = ts.parse_legacy_string(eb.get("end_time"))
    protocol_id = eb.get("protocolID") or a.get("protocolID")
    return {
        "epoch_block_uuid": eb.get("uuid") or a.get("uuid"),
        "epoch_group_uuid": epoch_group_uuid,
        "protocol_id": protocol_id,
        "data_file": eb.get("dataFile"),
        "start_time": start,
        "start_offset_hours": start_off,
        "end_time": end,
        "end_offset_hours": end_off,
        "parameters": eb.get("parameters") or {},
        "properties": _props(eb.get("properties")),
    }


def build_epoch_tuple(
    epoch: Dict[str, Any], epoch_block_uuid: str
) -> Dict[str, Any]:
    a = _attrs(epoch)
    start, start_off = ts.split_dotnet_pair(a, "startTime")
    end, end_off = ts.split_dotnet_pair(a, "endTime")
    # DJ JSON: epoch may carry ISO 8601 convenience fields too.
    if start is None:
        start = ts.parse_iso(epoch.get("start_time") or epoch.get("datetime"))
    if end is None:
        end = ts.parse_iso(epoch.get("end_time"))
    return {
        "epoch_uuid": epoch.get("uuid") or a.get("uuid"),
        "epoch_block_uuid": epoch_block_uuid,
        "start_time": start,
        "start_offset_hours": start_off,
        "end_time": end,
        "end_offset_hours": end_off,
        "is_partial": int(bool(a.get("isPartial", False))),
        "keywords": _join_keywords(epoch.get("keywords") or a.get("keywords")),
        "parameters": epoch.get("parameters") or {},
        "properties": _props(epoch.get("properties")),
    }


def build_response_tuple(
    epoch_uuid: str, device_name: str, resp: Dict[str, Any]
) -> Dict[str, Any]:
    input_time, input_off = ts.split_dotnet_pair(resp, "inputTime")
    return {
        "epoch_uuid": epoch_uuid,
        "device_name": device_name,
        "sample_rate": _to_float(resp.get("sampleRate")),
        "sample_rate_units": resp.get("sampleRateUnits"),
        "input_time": input_time,
        "input_offset_hours": input_off,
        "units": resp.get("units"),
        "h5path": resp.get("h5path"),
        "properties": {k: v for k, v in resp.items() if k not in (
            "sampleRate", "sampleRateUnits", "units", "h5path",
            "inputTimeDotNetDateTimeOffsetTicks",
            "inputTimeDotNetDateTimeOffsetOffsetHours",
        )},
    }


def build_stimulus_tuple(
    epoch_uuid: str, device_name: str, stim: Dict[str, Any]
) -> Dict[str, Any]:
    return {
        "epoch_uuid": epoch_uuid,
        "device_name": device_name,
        "stimulus_id": stim.get("stimulusID"),
        "sample_rate": _to_float(stim.get("sampleRate")),
        "sample_rate_units": stim.get("sampleRateUnits"),
        "units": stim.get("units"),
        "duration_seconds": _to_float(stim.get("durationSeconds")),
        "h5path": stim.get("h5path"),
        "params": stim.get("params") or stim.get("parameters") or {},
        "properties": {k: v for k, v in stim.items() if k not in (
            "stimulusID", "sampleRate", "sampleRateUnits", "units",
            "durationSeconds", "h5path", "params", "parameters",
        )},
    }


def build_background_tuple(
    epoch_uuid: str, device_name: str, bg: Dict[str, Any]
) -> Dict[str, Any]:
    return {
        "epoch_uuid": epoch_uuid,
        "device_name": device_name,
        "value": _to_float(bg.get("value")),
        "value_units": bg.get("valueUnits"),
        "sample_rate": _to_float(bg.get("sampleRate")),
        "sample_rate_units": bg.get("sampleRateUnits"),
        "properties": {k: v for k, v in bg.items() if k not in (
            "value", "valueUnits", "sampleRate", "sampleRateUnits",
        )},
    }


# ---------------------------------------------------------------------------
# Coercion helpers
# ---------------------------------------------------------------------------


def _to_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _join_keywords(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, str):
        return v or None
    if isinstance(v, (list, tuple)):
        joined = ",".join(str(x) for x in v if x)
        return joined or None
    return str(v)


# ---------------------------------------------------------------------------
# Public ingestion entry points (DB-bound)
# ---------------------------------------------------------------------------


def ingest_json(
    db: "Database",
    json_path: str | Path,
    *,
    h5_path: Optional[str | Path] = None,
    tags_path: Optional[str | Path] = None,
    skip_existing: bool = True,
) -> IngestReport:
    """Ingest a single ``*_dj.json`` file. ``db`` is a
    :class:`symphony_dj.connection.Database`."""
    json_path = Path(json_path).expanduser()
    if not json_path.exists():
        raise FileNotFoundError(json_path)

    with json_path.open("r") as f:
        document = json.load(f)

    report = IngestReport()
    report.files.append(str(json_path))

    # Top-level: an Experiment dict. parse_data.create_symphony_dict() puts the
    # Experiment fields at the root and the animals under "animals".
    exp_tuple = build_experiment_tuple(
        document, json_path=json_path, h5_path=Path(h5_path) if h5_path else None
    )
    if not exp_tuple["experiment_uuid"]:
        raise ValueError(f"{json_path} has no top-level experiment uuid")

    db.Experiment.insert1(exp_tuple, skip_duplicates=skip_existing)
    report.add("Experiment")
    experiment_uuid = exp_tuple["experiment_uuid"]

    for animal in document.get("animals", []):
        _ingest_animal(db, animal, experiment_uuid, report, skip_existing)

    if tags_path:
        _ingest_tags(db, Path(tags_path), experiment_uuid, report)

    logger.info("Ingested %s: %s", json_path.name, report)
    return report


def ingest_directory(
    db: "Database",
    root: str | Path,
    *,
    pattern: str = "*_dj.json",
    skip_existing: bool = True,
) -> IngestReport:
    """Ingest every ``*_dj.json`` under ``root`` (recursively)."""
    root = Path(root).expanduser()
    if not root.exists():
        raise FileNotFoundError(root)

    out = IngestReport()
    for path in sorted(root.rglob(pattern)):
        try:
            sub = ingest_json(db, path, skip_existing=skip_existing)
            out.merge(sub)
        except Exception as exc:
            out.errors.append(f"{path}: {exc}")
            logger.exception("Failed to ingest %s", path)
    return out


# ---------------------------------------------------------------------------
# Internal recursion
# ---------------------------------------------------------------------------


def _ingest_animal(db, animal, experiment_uuid, report, skip):
    row = build_animal_tuple(animal, experiment_uuid)
    if not row["animal_uuid"]:
        report.errors.append("Animal without uuid; skipped")
        return
    db.Animal.insert1(row, skip_duplicates=skip)
    report.add("Animal")
    for prep in animal.get("preparations", []):
        _ingest_preparation(db, prep, row["animal_uuid"], report, skip)


def _ingest_preparation(db, prep, animal_uuid, report, skip):
    row = build_preparation_tuple(prep, animal_uuid)
    if not row["preparation_uuid"]:
        report.errors.append("Preparation without uuid; skipped")
        return
    db.Preparation.insert1(row, skip_duplicates=skip)
    report.add("Preparation")
    for cell in prep.get("cells", []):
        _ingest_cell(db, cell, row["preparation_uuid"], report, skip)


def _ingest_cell(db, cell, preparation_uuid, report, skip):
    row = build_cell_tuple(cell, preparation_uuid)
    if not row["cell_uuid"]:
        report.errors.append("Cell without uuid; skipped")
        return
    db.Cell.insert1(row, skip_duplicates=skip)
    report.add("Cell")
    for eg in cell.get("epoch_groups", []):
        _ingest_epoch_group(db, eg, row["cell_uuid"], report, skip)


def _ingest_epoch_group(db, eg, cell_uuid, report, skip):
    row = build_epoch_group_tuple(eg, cell_uuid)
    if not row["epoch_group_uuid"]:
        report.errors.append("EpochGroup without uuid; skipped")
        return
    db.EpochGroup.insert1(row, skip_duplicates=skip)
    report.add("EpochGroup")
    for eb in eg.get("epoch_blocks", []):
        _ingest_epoch_block(db, eb, row["epoch_group_uuid"], report, skip)


def _ingest_epoch_block(db, eb, epoch_group_uuid, report, skip):
    row = build_epoch_block_tuple(eb, epoch_group_uuid)
    if not row["epoch_block_uuid"]:
        report.errors.append("EpochBlock without uuid; skipped")
        return
    if row["protocol_id"]:
        db.Protocol.insert1(
            {"protocol_id": row["protocol_id"]}, skip_duplicates=True
        )
        report.add("Protocol")
    db.EpochBlock.insert1(row, skip_duplicates=skip)
    report.add("EpochBlock")
    # The DJ spec uses "epochs" (plural). Legacy uses "epoch". Accept either.
    for epoch in eb.get("epochs") or eb.get("epoch") or []:
        _ingest_epoch(db, epoch, row["epoch_block_uuid"], report, skip)


def _ingest_epoch(db, epoch, epoch_block_uuid, report, skip):
    row = build_epoch_tuple(epoch, epoch_block_uuid)
    if not row["epoch_uuid"]:
        report.errors.append("Epoch without uuid; skipped")
        return
    db.Epoch.insert1(row, skip_duplicates=skip)
    report.add("Epoch")
    epoch_uuid = row["epoch_uuid"]

    for device, resp in (epoch.get("responses") or {}).items():
        db.Response.insert1(
            build_response_tuple(epoch_uuid, device, resp),
            skip_duplicates=skip,
        )
        report.add("Response")
    for device, stim in (epoch.get("stimuli") or {}).items():
        db.Stimulus.insert1(
            build_stimulus_tuple(epoch_uuid, device, stim),
            skip_duplicates=skip,
        )
        report.add("Stimulus")
    for device, bg in (epoch.get("backgrounds") or {}).items():
        db.Background.insert1(
            build_background_tuple(epoch_uuid, device, bg),
            skip_duplicates=skip,
        )
        report.add("Background")


# ---------------------------------------------------------------------------
# Tags sidecar
# ---------------------------------------------------------------------------


def _ingest_tags(db, path: Path, experiment_uuid: str, report: IngestReport):
    if not path.exists():
        report.errors.append(f"Tags file missing: {path}")
        return
    with path.open("r") as f:
        tags_doc = json.load(f) or {}
    rows = list(_parse_tags(tags_doc, experiment_uuid))
    if rows:
        db.Tag.insert(rows, skip_duplicates=True)
        report.add("Tag", len(rows))


def _parse_tags(doc: Dict[str, Any], experiment_uuid: str) -> Iterable[Dict[str, Any]]:
    for entity_uuid, entry in doc.items():
        for user, tag in (entry or {}).get("tags", []):
            yield {
                "entity_table": entry.get("table", ""),
                "entity_uuid": entity_uuid,
                "experiment_uuid": experiment_uuid,
                "user": user,
                "tag": tag,
            }
