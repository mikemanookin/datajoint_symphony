"""Integration tests for ``symphony_dj.query``."""
from __future__ import annotations

import pytest


@pytest.fixture
def populated_db(db, sample_json_path):
    db.ingest_json(sample_json_path)
    return db


@pytest.mark.integration
def test_levels(populated_db):
    levels = populated_db.query.levels()
    assert levels[0] == "experiment"
    assert "epoch_block" in levels
    assert levels[-1] == "background"


@pytest.mark.integration
def test_fields_for_epoch_block(populated_db):
    fields = dict(populated_db.query.fields("epoch_block"))
    assert fields["epoch_block_uuid"] == "string"
    assert fields["protocol_id"] == "string"
    # parameters and properties are blobs.
    assert fields["parameters"] in ("json",)
    assert fields["properties"] in ("json",)


@pytest.mark.integration
def test_tree_structure(populated_db, sample_json):
    uuid = sample_json["uuid"]
    tree = populated_db.query.tree(uuid, depth="cell")
    assert tree["experiment_uuid"] == uuid
    assert len(tree["animals"]) == 1
    assert tree["animals"][0]["preparations"][0]["cells"][0]["cell_type"] == "ParasolOff"


@pytest.mark.integration
def test_epochs_for_protocol(populated_db):
    sn = populated_db.query.epochs_for(
        protocol_id="manookinlab.protocols.SpatialNoise"
    )
    assert len(sn) == 2


@pytest.mark.integration
def test_tag_crud(populated_db, sample_json):
    epoch_uuid = (
        sample_json["animals"][0]["preparations"][0]["cells"][0]
        ["epoch_groups"][0]["epoch_blocks"][0]["epochs"][0]["uuid"]
    )
    populated_db.query.add_tag("Epoch", epoch_uuid, user="mike", tag="good")
    populated_db.query.add_tag("Epoch", epoch_uuid, user="mike", tag="good")  # idempotent
    tags = populated_db.query.tags(epoch_uuid)
    assert ("mike", "good") in tags
    populated_db.query.remove_tag(epoch_uuid, "mike", "good")
    assert ("mike", "good") not in populated_db.query.tags(epoch_uuid)


@pytest.mark.integration
def test_saved_queries(populated_db, tmp_path, monkeypatch):
    # Redirect download_dir to a tmp path so the test doesn't clobber the user's.
    from dataclasses import replace
    populated_db.config = replace(
        populated_db.config,
        paths=replace(populated_db.config.paths, download_dir=tmp_path),
    )
    populated_db._query = None  # noqa: SLF001 — force re-init
    populated_db.query.save("my_q", {"and": [{"cond": "x"}]})
    assert populated_db.query.load("my_q") == {"and": [{"cond": "x"}]}
    populated_db.query.delete_saved("my_q")
    assert "my_q" not in populated_db.query.saved_queries()
