"""Integration tests — full ingest into a real DataJoint MySQL."""
from __future__ import annotations

import pytest


@pytest.mark.integration
def test_ingest_sample_json_row_counts(db, sample_json_path):
    report = db.ingest_json(sample_json_path)
    assert not report.errors, f"Unexpected errors: {report.errors}"

    # Counts should match the fixture exactly.
    assert len(db.Experiment) == 1
    assert len(db.Animal) == 1
    assert len(db.Preparation) == 1
    assert len(db.Cell) == 1
    assert len(db.EpochGroup) == 1
    assert len(db.EpochBlock) == 1
    assert len(db.Epoch) == 2
    assert len(db.Response) == 2          # 1 device * 2 epochs
    assert len(db.Stimulus) == 1          # only first epoch has a stimulus
    assert len(db.Background) == 1
    assert len(db.Protocol) == 1


@pytest.mark.integration
def test_ingest_is_idempotent(db, sample_json_path):
    db.ingest_json(sample_json_path)
    n_before = len(db.Epoch)
    db.ingest_json(sample_json_path)
    n_after = len(db.Epoch)
    assert n_before == n_after


@pytest.mark.integration
def test_ingest_with_tags_sidecar(db, sample_json_path, sample_tags_path):
    report = db.ingest_json(sample_json_path, tags_path=sample_tags_path)
    assert not report.errors
    # Two tags on one epoch + one tag on one cell = 3.
    assert len(db.Tag) == 3


@pytest.mark.integration
def test_protocol_autocreate(db, sample_json_path):
    db.ingest_json(sample_json_path)
    assert (db.Protocol & {
        "protocol_id": "manookinlab.protocols.SpatialNoise"
    })


@pytest.mark.integration
def test_delete_cascades(db, sample_json_path):
    db.ingest_json(sample_json_path)
    assert len(db.Epoch) == 2
    (db.Experiment & "experiment_uuid='exp-aaaaaaaa-1111-1111-1111-111111111111'") \
        .delete_quick()
    # FK-cascade should remove everything below.
    assert len(db.Animal) == 0
    assert len(db.Preparation) == 0
    assert len(db.Cell) == 0
    assert len(db.Epoch) == 0
    assert len(db.Response) == 0


@pytest.mark.integration
def test_uuid_round_trip(db, sample_json, sample_json_path):
    db.ingest_json(sample_json_path)
    uuid_in_json = sample_json["uuid"]
    rows = (db.Experiment & {"experiment_uuid": uuid_in_json}).fetch()
    assert len(rows) == 1
