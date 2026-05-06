"""Schema declaration tests (no DB).

These tests assert structural invariants — every table declares, FK
graph matches the spec, primary keys are UUIDs of the expected width.
They run against a real ``dj.Schema`` against the same MySQL the
integration suite uses, but the schema is dropped immediately.
"""
from __future__ import annotations

import datajoint as dj
import pytest

from symphony_dj.schema import (
    HIERARCHY,
    PARENT_OF,
    UUID_KEY,
    declare,
)


def test_module_constants_consistent():
    # Every parent_of entry maps to a known table.
    for child, parent in PARENT_OF.items():
        assert parent in (HIERARCHY + ["Experiment"]) or parent in HIERARCHY
    # Hierarchy in canonical order.
    assert HIERARCHY[0] == "Experiment"
    assert "Epoch" in HIERARCHY
    assert HIERARCHY.index("Animal") < HIERARCHY.index("Cell")
    assert HIERARCHY.index("Epoch") < HIERARCHY.index("Response")


def test_uuid_key_columns_match_expected_names():
    assert UUID_KEY["Experiment"] == "experiment_uuid"
    assert UUID_KEY["Animal"] == "animal_uuid"
    assert UUID_KEY["Preparation"] == "preparation_uuid"
    assert UUID_KEY["Cell"] == "cell_uuid"
    assert UUID_KEY["EpochGroup"] == "epoch_group_uuid"
    assert UUID_KEY["EpochBlock"] == "epoch_block_uuid"
    assert UUID_KEY["Epoch"] == "epoch_uuid"


def test_declare_returns_all_tables(db):
    """Names and types of every table the package declares."""
    expected = {
        "Protocol",
        "Experiment", "Animal", "Preparation", "Cell",
        "EpochGroup", "EpochBlock", "Epoch",
        "Response", "Stimulus", "Background",
        "Note", "Tag",
        "SortingChunk", "SortedCell", "CellTypeFile", "SortedCellType",
    }
    actual = set(db._tables.keys())  # noqa: SLF001
    assert actual == expected


def test_primary_keys_are_36char_uuid(db):
    for table_name in (
        "Experiment", "Animal", "Preparation", "Cell",
        "EpochGroup", "EpochBlock", "Epoch",
    ):
        cls = getattr(db, table_name)
        pk_cols = [c for c in cls.heading.attributes if cls.heading.attributes[c].in_key]
        assert len(pk_cols) == 1, f"{table_name} should have exactly 1 PK"
        pk = cls.heading.attributes[pk_cols[0]]
        assert pk.type == "varchar(36)", f"{table_name}.{pk.name} type {pk.type}"


def test_foreign_key_graph(db):
    """Every parent_of entry corresponds to a real FK in the schema."""
    for child, parent in PARENT_OF.items():
        if child in ("Response", "Stimulus", "Background"):
            # FK to Epoch via the compound PK.
            ancestors = getattr(db, child).parents()
            assert any("epoch" in p for p in ancestors), (
                f"{child} missing FK to Epoch (parents={ancestors})"
            )
            continue
        ancestors = getattr(db, child).parents()
        # Convert table refs (`schema.\`tablename\``) to lowercase tokens.
        joined = " ".join(ancestors).lower()
        # parent name in snake-case
        snake = "".join(
            "_" + c.lower() if c.isupper() and i else c.lower()
            for i, c in enumerate(parent)
        )
        assert snake in joined, (
            f"{child} missing FK to {parent}: parents={ancestors}"
        )


def test_diagram_renders(db):
    """``dj.Diagram(db.schema)`` constructs without raising."""
    diagram = dj.Diagram(db.schema)
    # No assertion on render; we just want to make sure construction works.
    assert diagram is not None


@pytest.mark.parametrize("table", [
    "Experiment", "Animal", "Preparation", "Cell",
    "EpochGroup", "EpochBlock", "Epoch",
])
def test_properties_column_is_blob(db, table):
    cls = getattr(db, table)
    assert "properties" in cls.heading.attributes
    typ = cls.heading.attributes["properties"].type
    assert typ in ("longblob", "blob", "mediumblob"), (
        f"{table}.properties type={typ}"
    )
