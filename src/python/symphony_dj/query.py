"""Query helpers for the Symphony DataJoint schema.

These wrap common navigation / filtering patterns over the relational
schema so notebook code stays terse. Every helper returns a *DataJoint
expression* (queryable, joinable) wherever possible — fetching is left
to the caller.

See ``spec/04_query_api.md``.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import datajoint as dj

from .schema import HIERARCHY, PARENT_OF, UUID_KEY

logger = logging.getLogger(__name__)


_HIERARCHY_LOWER = [
    "experiment", "animal", "preparation", "cell",
    "epoch_group", "epoch_block", "epoch",
    "response", "stimulus", "background",
]


def _fmt_table(snake: str) -> str:
    """``epoch_group`` → ``EpochGroup``."""
    return "".join(part.capitalize() for part in snake.split("_"))


class Query:
    """Bound to a :class:`symphony_dj.Database`."""

    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def levels(self) -> List[str]:
        """Hierarchy table names in order, snake_case
        (``['experiment', 'animal', ...]``)."""
        return list(_HIERARCHY_LOWER)

    def fields(self, table_name: str) -> List[Tuple[str, str]]:
        """List of ``(column_name, type)`` for a table.

        ``type`` is one of ``'date'``, ``'json'`` (for longblob columns),
        ``'string'``, ``'numeric'``.
        """
        cls = getattr(self.db, _fmt_table(table_name), None)
        if cls is None:
            raise KeyError(table_name)
        out: List[Tuple[str, str]] = []
        for name, attr in cls.heading.attributes.items():
            if attr.type.startswith("datetime") or attr.type == "timestamp":
                t = "date"
            elif attr.type in ("longblob", "blob", "mediumblob", "json"):
                t = "json"
            elif attr.string:
                t = "string"
            elif attr.numeric:
                t = "numeric"
            else:
                t = "other"
            out.append((name, t))
        return out

    # ------------------------------------------------------------------
    # Hierarchy traversal
    # ------------------------------------------------------------------

    def tree(
        self, experiment_uuid: str, depth: str = "epoch"
    ) -> Dict[str, Any]:
        """Return a nested-dict tree rooted at one experiment.

        ``depth`` caps the traversal; pass any of ``HIERARCHY`` (snake or
        Pascal). Default reaches Epochs but stops short of per-device
        rows for performance.
        """
        depth_lower = depth.lower().replace("_", "")
        depth_index = {
            "experiment": 0, "animal": 1, "preparation": 2, "cell": 3,
            "epochgroup": 4, "epochblock": 5, "epoch": 6,
        }.get(depth_lower)
        if depth_index is None:
            raise ValueError(f"Unknown depth: {depth!r}")

        exp = (self.db.Experiment & {"experiment_uuid": experiment_uuid}).fetch1()
        out = dict(exp)
        if depth_index >= 1:
            out["animals"] = self._children(
                "Experiment", experiment_uuid, "Animal", depth_index, 1
            )
        return out

    def _children(self, parent_table, parent_uuid, child_table, max_depth, cur_depth):
        parent_key = UUID_KEY[parent_table]
        child_key = UUID_KEY.get(child_table)
        cls = getattr(self.db, child_table)
        rows = (cls & {parent_key: parent_uuid}).to_dicts()
        out = []
        # Identify the *single* hierarchy child of the current child, if any.
        next_table = _next_in_hierarchy(child_table)
        for r in rows:
            d = dict(r)
            if cur_depth < max_depth and next_table:
                d_key = "animals" if next_table == "Animal" else (
                    f"{next_table.lower()[0]}{next_table[1:].lower()}s"
                )
                # Use a friendlier plural mapping:
                d_key = _PLURAL[next_table]
                d[d_key] = self._children(
                    child_table, r[child_key], next_table, max_depth, cur_depth + 1
                )
            out.append(d)
        return out

    # ------------------------------------------------------------------
    # Filtered datasets
    # ------------------------------------------------------------------

    def epochs_for(
        self, *, protocol_id: Optional[str] = None, **filters: Any
    ) -> dj.expression.QueryExpression:
        """Return ``Epoch * EpochBlock * EpochGroup * Cell * Preparation *
        Animal * Experiment`` filtered by any kwargs.

        Multiple tables in the hierarchy share column names (``label``,
        ``start_time``, ``parameters``, ``properties``). DataJoint 2.0
        refuses to auto-merge same-named attributes from different
        lineages, so we project each table to a clean, uniquely-named
        view before joining. Open blobs (``parameters``/``properties``)
        are dropped from the joined view — fetch the original table by
        UUID if you need them.
        """
        # NOTE: dj.proj signature is .proj(*positional, **renamed). Python
        # syntax requires positional args before keyword args.
        epoch = self.db.Epoch.proj(
            "is_partial",
            epoch_start="start_time",
            epoch_end="end_time",
            epoch_offset_hours="start_offset_hours",
        )
        epoch_block = self.db.EpochBlock.proj(
            "protocol_id",
            "data_file",
            block_start="start_time",
            block_end="end_time",
        )
        epoch_group = self.db.EpochGroup.proj(
            group_label="label",
            group_start="start_time",
            group_end="end_time",
        )
        cell = self.db.Cell.proj(
            cell_label="label",
            cell_type="cell_type",
        )
        preparation = self.db.Preparation.proj(
            "bath_solution",
            "preparation_type",
            "region",
            "array_pitch",
            prep_label="label",
        )
        animal = self.db.Animal.proj(
            "animal_id",
            "species",
            "sex",
            "age",
            "weight",
            animal_label="label",
        )
        experiment = self.db.Experiment.proj(
            "purpose",
            "experimenter",
            "institution",
            "lab",
            "project",
            "rig",
            "rig_type",
        )

        joined = (
            epoch * epoch_block * epoch_group
            * cell * preparation * animal * experiment
        )

        if protocol_id is not None:
            joined = joined & {"protocol_id": protocol_id}
        if filters:
            joined = joined & filters
        return joined

    def responses(self, epoch_uuid: str) -> dj.expression.QueryExpression:
        return self.db.Response & {"epoch_uuid": epoch_uuid}

    def stimuli(self, epoch_uuid: str) -> dj.expression.QueryExpression:
        return self.db.Stimulus & {"epoch_uuid": epoch_uuid}

    def backgrounds(self, epoch_uuid: str) -> dj.expression.QueryExpression:
        return self.db.Background & {"epoch_uuid": epoch_uuid}

    # ------------------------------------------------------------------
    # Saved queries (JSON-backed)
    # ------------------------------------------------------------------

    def _saved_path(self) -> Path:
        d = self.db.config.paths.download_dir
        d.mkdir(parents=True, exist_ok=True)
        return d / "queries.json"

    def saved_queries(self) -> Dict[str, Any]:
        path = self._saved_path()
        if not path.exists():
            return {}
        with path.open("r") as f:
            return json.load(f) or {}

    def save(self, name: str, query_obj: Dict[str, Any]) -> None:
        existing = self.saved_queries()
        existing[name] = query_obj
        with self._saved_path().open("w") as f:
            json.dump(existing, f, indent=2)

    def load(self, name: str) -> Dict[str, Any]:
        return self.saved_queries()[name]

    def delete_saved(self, name: str) -> None:
        existing = self.saved_queries()
        existing.pop(name, None)
        with self._saved_path().open("w") as f:
            json.dump(existing, f, indent=2)

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    def tags(self, entity_uuid: str) -> List[Tuple[str, str]]:
        rows = (self.db.Tag & {"entity_uuid": entity_uuid}).to_dicts()
        return [(r["user"], r["tag"]) for r in rows]

    def add_tag(
        self, entity_table: str, entity_uuid: str, user: str, tag: str
    ) -> None:
        # Resolve experiment_uuid for the FK.
        experiment_uuid = self._experiment_uuid_for(entity_table, entity_uuid)
        self.db.Tag.insert1(
            {
                "entity_table": entity_table.lower(),
                "entity_uuid": entity_uuid,
                "experiment_uuid": experiment_uuid,
                "user": user,
                "tag": tag,
            },
            skip_duplicates=True,
        )

    def remove_tag(self, entity_uuid: str, user: str, tag: str) -> None:
        (self.db.Tag & {
            "entity_uuid": entity_uuid, "user": user, "tag": tag
        }).delete_quick()

    def _experiment_uuid_for(self, entity_table: str, entity_uuid: str) -> str:
        """Walk up the hierarchy from any entity to its Experiment."""
        table = _fmt_table(entity_table)
        if table == "Experiment":
            return entity_uuid
        cls = getattr(self.db, table)
        key_col = UUID_KEY.get(table) or "epoch_uuid"
        # Join up to Experiment via PARENT_OF.
        # Easiest: iteratively fetch the parent's uuid.
        cur_table, cur_uuid = table, entity_uuid
        while cur_table != "Experiment":
            parent = PARENT_OF[cur_table]
            cur_cls = getattr(self.db, cur_table)
            row = (cur_cls & {UUID_KEY[cur_table] if cur_table in UUID_KEY else key_col: cur_uuid}).fetch1()
            cur_uuid = row[UUID_KEY[parent] if parent in UUID_KEY else "experiment_uuid"]
            cur_table = parent
        return cur_uuid


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_PLURAL = {
    "Animal": "animals",
    "Preparation": "preparations",
    "Cell": "cells",
    "EpochGroup": "epoch_groups",
    "EpochBlock": "epoch_blocks",
    "Epoch": "epochs",
}

_NEXT = {
    "Experiment": "Animal",
    "Animal": "Preparation",
    "Preparation": "Cell",
    "Cell": "EpochGroup",
    "EpochGroup": "EpochBlock",
    "EpochBlock": "Epoch",
}


def _next_in_hierarchy(table: str) -> Optional[str]:
    return _NEXT.get(table)
