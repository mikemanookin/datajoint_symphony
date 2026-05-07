"""DataJoint 2.0 schema declarations for the Symphony pipeline.

Tables follow ``spec/01_schema.md``. Every Symphony entity uses its
upstream UUID as the single primary key (see ADR-0001). All "open"
metadata fields (``properties``, ``parameters``, ``params``) are
declared as ``json`` so DataJoint 2.0's JSON-category encoder
auto-converts Python dicts on insert / fetch (see ADR-0002).

Usage::

    import datajoint as dj
    from symphony_dj import schema as sdj_schema

    schema = dj.Schema("symphony")
    tables = sdj_schema.declare(schema)
    tables["Experiment"].insert1({...})

The ``declare`` function returns a dict of class→class mapping for
convenience; :class:`symphony_dj.connection.Database` wraps this so
callers see the table names as attributes.
"""
from __future__ import annotations

from typing import Any, Dict, Type

import datajoint as dj


# ---------------------------------------------------------------------------
# Ordered list of hierarchy tables (used by ingest, query helpers).
# ---------------------------------------------------------------------------

HIERARCHY = [
    "Experiment",
    "Animal",
    "Preparation",
    "Cell",
    "EpochGroup",
    "EpochBlock",
    "Epoch",
    "Response",
    "Stimulus",
    "Background",
]


def declare(schema: dj.Schema) -> Dict[str, Type[Any]]:
    """Declare every table on the given ``dj.Schema`` and return a name→class map.

    This is wrapped in a function (rather than declared at module import time)
    so the schema name is configurable per ``AppConfig``. Re-calling against
    the same schema is safe — DataJoint caches the class definitions.
    """

    @schema
    class Protocol(dj.Lookup):
        definition = """
        # Symphony protocol identifier, e.g. manookinlab.protocols.SpatialNoise
        protocol_id : varchar(255)
        ---
        display_name = NULL : varchar(255)
        description = NULL : varchar(1024)
        """

    @schema
    class Experiment(dj.Manual):
        definition = """
        # Top-level experiment; one row per source HDF5 file.
        experiment_uuid : varchar(36)
        ---
        purpose = NULL : varchar(255)
        start_time = NULL : datetime(6)
        start_offset_hours = NULL : float32
        end_time = NULL : datetime(6)
        end_offset_hours = NULL : float32
        keywords = NULL : varchar(1024)
        experimenter = NULL : varchar(255)
        institution = NULL : varchar(255)
        lab = NULL : varchar(255)
        project = NULL : varchar(255)
        rig = NULL : varchar(255)
        rig_type = NULL : enum('PATCH','MEA')
        h5_path = NULL : varchar(1023)
        json_path = NULL : varchar(1023)
        date_added = CURRENT_TIMESTAMP : datetime
        properties : json
        """

    @schema
    class Animal(dj.Manual):
        definition = """
        # Animal (lab nomenclature; 'A1', 'A2', ...)
        animal_uuid : varchar(36)
        ---
        -> Experiment
        label = NULL : varchar(255)
        start_time = NULL : datetime(6)
        start_offset_hours = NULL : float32
        animal_id = NULL : varchar(255)
        description = NULL : varchar(1024)
        sex = NULL : varchar(32)
        age = NULL : varchar(64)
        weight = NULL : varchar(64)
        dark_adaptation = NULL : varchar(255)
        species = NULL : varchar(255)
        properties : json
        """

    @schema
    class Preparation(dj.Manual):
        definition = """
        # Preparation (e.g. 'OD', 'OS')
        preparation_uuid : varchar(36)
        ---
        -> Animal
        label = NULL : varchar(255)
        start_time = NULL : datetime(6)
        start_offset_hours = NULL : float32
        bath_solution = NULL : varchar(255)
        preparation_type = NULL : varchar(255)
        region = NULL : varchar(255)
        array_pitch = NULL : varchar(32)
        properties : json
        """

    @schema
    class Cell(dj.Manual):
        definition = """
        # Recorded cell
        cell_uuid : varchar(36)
        ---
        -> Preparation
        label = NULL : varchar(255)
        start_time = NULL : datetime(6)
        start_offset_hours = NULL : float32
        cell_type = NULL : varchar(255)
        properties : json
        """

    @schema
    class EpochGroup(dj.Manual):
        definition = """
        # Group of epoch blocks recorded under a cell
        epoch_group_uuid : varchar(36)
        ---
        -> Cell
        label = NULL : varchar(255)
        start_time = NULL : datetime(6)
        start_offset_hours = NULL : float32
        end_time = NULL : datetime(6)
        end_offset_hours = NULL : float32
        keywords = NULL : varchar(1024)
        properties : json
        """

    # Forward-declared so EpochBlock can FK to it.
    @schema
    class SortingChunk(dj.Manual):
        definition = """
        # Spike-sorting chunk (analysis layer; populated by external pipelines)
        sorting_chunk_id : int unsigned auto_increment
        ---
        -> Experiment
        chunk_name : varchar(255)
        unique index (experiment_uuid, chunk_name)
        """

    @schema
    class EpochBlock(dj.Manual):
        definition = """
        # Epoch block: one continuous run of a single protocol
        epoch_block_uuid : varchar(36)
        ---
        -> EpochGroup
        -> Protocol
        -> [nullable] SortingChunk
        data_file = NULL : varchar(1023)
        start_time = NULL : datetime(6)
        start_offset_hours = NULL : float32
        end_time = NULL : datetime(6)
        end_offset_hours = NULL : float32
        parameters : json
        properties : json
        """

    @schema
    class Epoch(dj.Manual):
        definition = """
        # Single epoch (one stimulus presentation)
        epoch_uuid : varchar(36)
        ---
        -> EpochBlock
        start_time = NULL : datetime(6)
        start_offset_hours = NULL : float32
        end_time = NULL : datetime(6)
        end_offset_hours = NULL : float32
        is_partial = 0 : bool
        keywords = NULL : varchar(1024)
        parameters : json
        properties : json
        """

    @schema
    class Response(dj.Manual):
        definition = """
        # Per-device response (metadata only; raw data stays in the HDF5)
        -> Epoch
        device_name : varchar(127)
        ---
        sample_rate = NULL : float64
        sample_rate_units = NULL : varchar(31)
        input_time = NULL : datetime(6)
        input_offset_hours = NULL : float32
        units = NULL : varchar(31)
        h5path = NULL : varchar(1023)
        properties : json
        """

    @schema
    class Stimulus(dj.Manual):
        definition = """
        # Per-device stimulus
        -> Epoch
        device_name : varchar(127)
        ---
        stimulus_id = NULL : varchar(255)
        sample_rate = NULL : float64
        sample_rate_units = NULL : varchar(31)
        units = NULL : varchar(31)
        duration_seconds = NULL : float64
        h5path = NULL : varchar(1023)
        params : json
        properties : json
        """

    @schema
    class Background(dj.Manual):
        definition = """
        # Per-device background level
        -> Epoch
        device_name : varchar(127)
        ---
        value = NULL : float64
        value_units = NULL : varchar(31)
        sample_rate = NULL : float64
        sample_rate_units = NULL : varchar(31)
        properties : json
        """

    @schema
    class Note(dj.Manual):
        definition = """
        # Free-text experimenter note attached to any entity
        note_id : int unsigned auto_increment
        ---
        entity_table : varchar(63)
        entity_uuid : varchar(36)
        note_time = NULL : datetime(6)
        note_offset_hours = NULL : float32
        text : varchar(4095)
        """

    @schema
    class Tag(dj.Manual):
        definition = """
        # User-applied tag on any entity
        tag_id : int unsigned auto_increment
        ---
        entity_table : varchar(63)
        entity_uuid : varchar(36)
        -> Experiment
        user : varchar(63)
        tag : varchar(255)
        unique index (entity_uuid, user, tag)
        """

    @schema
    class SortedCell(dj.Manual):
        definition = """
        # Algorithm-identified cell from a sorting chunk
        sorted_cell_id : int unsigned auto_increment
        ---
        -> SortingChunk
        algorithm : varchar(127)
        cluster_id : int32
        unique index (sorting_chunk_id, algorithm, cluster_id)
        """

    @schema
    class CellTypeFile(dj.Manual):
        definition = """
        # Human-curated cell-typing file
        cell_type_file_id : int unsigned auto_increment
        ---
        -> SortingChunk
        algorithm : varchar(127)
        file_name : varchar(255)
        unique index (sorting_chunk_id, algorithm, file_name)
        """

    @schema
    class SortedCellType(dj.Manual):
        definition = """
        # A cell type assignment from a CellTypeFile to a SortedCell
        -> SortedCell
        -> CellTypeFile
        ---
        cell_type : varchar(127)
        """

    return {
        "Protocol": Protocol,
        "Experiment": Experiment,
        "Animal": Animal,
        "Preparation": Preparation,
        "Cell": Cell,
        "EpochGroup": EpochGroup,
        "EpochBlock": EpochBlock,
        "Epoch": Epoch,
        "Response": Response,
        "Stimulus": Stimulus,
        "Background": Background,
        "Note": Note,
        "Tag": Tag,
        "SortingChunk": SortingChunk,
        "SortedCell": SortedCell,
        "CellTypeFile": CellTypeFile,
        "SortedCellType": SortedCellType,
    }


# ---------------------------------------------------------------------------
# UUID-key column name per hierarchy table — used by ingest and query helpers.
# ---------------------------------------------------------------------------

UUID_KEY = {
    "Experiment": "experiment_uuid",
    "Animal": "animal_uuid",
    "Preparation": "preparation_uuid",
    "Cell": "cell_uuid",
    "EpochGroup": "epoch_group_uuid",
    "EpochBlock": "epoch_block_uuid",
    "Epoch": "epoch_uuid",
}

# Parent-child links among the hierarchy.
PARENT_OF = {
    "Animal": "Experiment",
    "Preparation": "Animal",
    "Cell": "Preparation",
    "EpochGroup": "Cell",
    "EpochBlock": "EpochGroup",
    "Epoch": "EpochBlock",
    "Response": "Epoch",
    "Stimulus": "Epoch",
    "Background": "Epoch",
}
