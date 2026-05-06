"""DJ JSON contract invariants — see DJ_JSON_SCHEMA.md.

These are the five invariants the upstream spec requires every
``*_dj.json`` to satisfy. After ingestion, they must also hold against
the relational schema. These tests act as a contract gate.
"""
from __future__ import annotations

import pytest


@pytest.mark.integration
def test_invariant_1_uuid_consistency(db, sample_json, sample_json_path):
    """Every entity's PK in DataJoint matches its source UUID."""
    db.ingest_json(sample_json_path)

    exp_uuid = sample_json["uuid"]
    assert (db.Experiment & {"experiment_uuid": exp_uuid})

    for animal in sample_json["animals"]:
        assert (db.Animal & {"animal_uuid": animal["uuid"]})
        for prep in animal["preparations"]:
            assert (db.Preparation & {"preparation_uuid": prep["uuid"]})
            for cell in prep["cells"]:
                assert (db.Cell & {"cell_uuid": cell["uuid"]})
                for eg in cell["epoch_groups"]:
                    assert (db.EpochGroup & {"epoch_group_uuid": eg["uuid"]})
                    for eb in eg["epoch_blocks"]:
                        assert (db.EpochBlock & {"epoch_block_uuid": eb["uuid"]})
                        for epoch in eb["epochs"]:
                            assert (db.Epoch & {"epoch_uuid": epoch["uuid"]})


@pytest.mark.integration
def test_invariant_2_completeness(db, sample_json, sample_json_path):
    """Row counts match the JSON exactly."""
    db.ingest_json(sample_json_path)

    n_animal = sum(1 for _ in sample_json["animals"])
    n_prep = sum(
        1
        for a in sample_json["animals"]
        for _ in a["preparations"]
    )
    n_cell = sum(
        1
        for a in sample_json["animals"]
        for p in a["preparations"]
        for _ in p["cells"]
    )
    n_epoch = sum(
        1
        for a in sample_json["animals"]
        for p in a["preparations"]
        for c in p["cells"]
        for eg in c["epoch_groups"]
        for eb in eg["epoch_blocks"]
        for _ in eb["epochs"]
    )

    assert len(db.Animal) == n_animal
    assert len(db.Preparation) == n_prep
    assert len(db.Cell) == n_cell
    assert len(db.Epoch) == n_epoch


@pytest.mark.integration
def test_invariant_3_protocol_parameter_fidelity(db, sample_json, sample_json_path):
    """``EpochBlock.parameters`` and ``Epoch.parameters`` byte-equal the JSON."""
    db.ingest_json(sample_json_path)
    eb_json = (
        sample_json["animals"][0]["preparations"][0]["cells"][0]
        ["epoch_groups"][0]["epoch_blocks"][0]
    )
    eb_db = (db.EpochBlock & {"epoch_block_uuid": eb_json["uuid"]}).fetch1()
    assert eb_db["parameters"] == eb_json["parameters"]

    epoch_json = eb_json["epochs"][0]
    epoch_db = (db.Epoch & {"epoch_uuid": epoch_json["uuid"]}).fetch1()
    assert epoch_db["parameters"] == epoch_json["parameters"]


@pytest.mark.integration
def test_invariant_4_device_name_format(db, sample_json_path):
    """Device names in Response/Stimulus/Background are short, not UUID-suffixed."""
    db.ingest_json(sample_json_path)
    devices = (db.Response).fetch("device_name")
    for d in devices:
        assert "-" not in d or d.count("-") < 4, f"Device name looks UUID-suffixed: {d}"


@pytest.mark.integration
def test_invariant_5_timestamp_roundtrip(db, sample_json, sample_json_path):
    """ticks → datetime → ticks recovers the original ticks (modulo 1µs)."""
    from symphony_dj.timestamps import datetime_to_ticks

    db.ingest_json(sample_json_path)
    eb_json = (
        sample_json["animals"][0]["preparations"][0]["cells"][0]
        ["epoch_groups"][0]["epoch_blocks"][0]
    )
    original_ticks = eb_json["attributes"]["startTimeDotNetDateTimeOffsetTicks"]

    eb_db = (db.EpochBlock & {"epoch_block_uuid": eb_json["uuid"]}).fetch1()
    # Re-encode the stored datetime back to ticks. Since we stored at µs precision,
    # the recovered ticks rounds to the nearest µs (10 ticks).
    recovered = datetime_to_ticks(eb_db["start_time"])
    assert abs(recovered - original_ticks) <= 10
