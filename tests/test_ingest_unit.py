"""Unit tests for ``symphony_dj.ingest`` tuple builders (no DB)."""
from __future__ import annotations

import pytest

from symphony_dj.ingest import (
    build_animal_tuple,
    build_background_tuple,
    build_cell_tuple,
    build_epoch_block_tuple,
    build_epoch_group_tuple,
    build_epoch_tuple,
    build_experiment_tuple,
    build_preparation_tuple,
    build_response_tuple,
    build_stimulus_tuple,
)


def test_experiment_from_fixture(sample_json):
    row = build_experiment_tuple(sample_json)
    assert row["experiment_uuid"] == "aaaaaaaa-1111-1111-1111-111111111111"
    assert row["lab"] == "Manookin"
    assert row["rig_type"] == "PATCH"
    assert row["start_offset_hours"] == -7.0
    assert row["start_time"] is not None
    assert row["end_time"] is not None
    assert row["keywords"] == "test,fixture"


def test_animal_from_fixture(sample_json):
    animal = sample_json["animals"][0]
    row = build_animal_tuple(animal, "exp-XYZ")
    assert row["animal_uuid"] == "bbbbbbbb-2222-2222-2222-222222222222"
    assert row["experiment_uuid"] == "exp-XYZ"
    assert row["label"] == "A1"
    assert row["species"] == "macaque"
    assert row["animal_id"] == "A1"
    assert row["sex"] == "M"


def test_preparation_from_fixture(sample_json):
    prep = sample_json["animals"][0]["preparations"][0]
    row = build_preparation_tuple(prep, "ani-XYZ")
    assert row["preparation_uuid"] == "cccccccc-3333-3333-3333-333333333333"
    assert row["animal_uuid"] == "ani-XYZ"
    assert row["bath_solution"] == "Ames"
    # NB: the JSON key is singular `preparation` for the type.
    assert row["preparation_type"] == "wholemount"
    assert row["region"] == "central"


def test_cell_from_fixture(sample_json):
    cell = sample_json["animals"][0]["preparations"][0]["cells"][0]
    row = build_cell_tuple(cell, "pre-XYZ")
    assert row["cell_uuid"] == "dddddddd-4444-4444-4444-444444444444"
    assert row["preparation_uuid"] == "pre-XYZ"
    assert row["cell_type"] == "ParasolOff"


def test_epoch_group_from_fixture(sample_json):
    eg = (
        sample_json["animals"][0]["preparations"][0]["cells"][0]
        ["epoch_groups"][0]
    )
    row = build_epoch_group_tuple(eg, "cel-XYZ")
    assert row["epoch_group_uuid"] == "eeeeeeee-5555-5555-5555-555555555555"
    assert row["cell_uuid"] == "cel-XYZ"
    assert row["start_time"] is not None
    assert row["end_time"] is not None


def test_epoch_block_from_fixture(sample_json):
    eb = (
        sample_json["animals"][0]["preparations"][0]["cells"][0]
        ["epoch_groups"][0]["epoch_blocks"][0]
    )
    row = build_epoch_block_tuple(eb, "egp-XYZ")
    assert row["epoch_block_uuid"] == "ffffffff-6666-6666-6666-666666666666"
    assert row["epoch_group_uuid"] == "egp-XYZ"
    assert row["protocol_id"] == "manookinlab.protocols.SpatialNoise"
    assert row["data_file"] == "20260410H.h5"
    assert row["parameters"]["stixelSize"] == 30
    assert row["properties"]["epochStarts"] == [0.0, 1.5]


def test_epoch_from_fixture(sample_json):
    epoch = (
        sample_json["animals"][0]["preparations"][0]["cells"][0]
        ["epoch_groups"][0]["epoch_blocks"][0]["epochs"][0]
    )
    row = build_epoch_tuple(epoch, "ebl-XYZ")
    assert row["epoch_uuid"] == "11111111-7777-7777-7777-777777777777"
    assert row["epoch_block_uuid"] == "ebl-XYZ"
    assert row["is_partial"] == 0
    assert row["parameters"]["noiseSeed"] == 1


def test_response_tuple_from_fixture(sample_json):
    epoch = (
        sample_json["animals"][0]["preparations"][0]["cells"][0]
        ["epoch_groups"][0]["epoch_blocks"][0]["epochs"][0]
    )
    resp = epoch["responses"]["Amp1"]
    row = build_response_tuple(epoch["uuid"], "Amp1", resp)
    assert row["epoch_uuid"] == epoch["uuid"]
    assert row["device_name"] == "Amp1"
    assert row["sample_rate"] == 10000.0
    assert row["units"] == "pA"
    assert row["input_offset_hours"] == -7.0


def test_stimulus_tuple_from_fixture(sample_json):
    epoch = (
        sample_json["animals"][0]["preparations"][0]["cells"][0]
        ["epoch_groups"][0]["epoch_blocks"][0]["epochs"][0]
    )
    stim = epoch["stimuli"]["LightCrafter"]
    row = build_stimulus_tuple(epoch["uuid"], "LightCrafter", stim)
    assert row["stimulus_id"] == "manookinlab.stimuli.SpatialNoise"
    assert row["sample_rate"] == 60.0
    assert row["params"] == {"stixelSize": 30}


def test_background_tuple_from_fixture(sample_json):
    epoch = (
        sample_json["animals"][0]["preparations"][0]["cells"][0]
        ["epoch_groups"][0]["epoch_blocks"][0]["epochs"][0]
    )
    bg = epoch["backgrounds"]["Amp1"]
    row = build_background_tuple(epoch["uuid"], "Amp1", bg)
    assert row["value"] == 0.0
    assert row["value_units"] == "pA"


def test_optional_fields_become_none():
    minimal_animal = {
        "uuid": "x",
        "label": "A1",
        "attributes": {"uuid": "x", "label": "A1"},
        "properties": {},
    }
    row = build_animal_tuple(minimal_animal, "exp-XYZ")
    # No species, sex, etc. — must not raise, must be None.
    assert row["species"] is None
    assert row["sex"] is None
    assert row["properties"] == {}


def test_keywords_list_joined():
    exp = {
        "uuid": "x",
        "attributes": {"uuid": "x", "keywords": ["a", "b", "c"]},
        "properties": {},
    }
    row = build_experiment_tuple(exp)
    assert row["keywords"] == "a,b,c"


def test_keywords_string_passthrough():
    exp = {
        "uuid": "x",
        "attributes": {"uuid": "x", "keywords": "single,kw"},
        "properties": {},
    }
    row = build_experiment_tuple(exp)
    assert row["keywords"] == "single,kw"
