"""On-demand HDF5 sample reads.

Raw response/stimulus arrays are not duplicated into MySQL; they live in
the source ``.h5`` files. These helpers resolve a UUID + device to the
right HDF5 path and return a numpy array.

The functions deliberately import h5py lazily so the rest of the package
remains usable in environments without HDF5 installed.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


def _import_h5py():
    try:
        import h5py  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "h5py is required for raw sample reads. Install with: pip install h5py"
        ) from exc
    return h5py


def open_experiment_file(h5_path: str | Path):
    """Return an ``h5py.File`` opened for read on the experiment file."""
    h5py = _import_h5py()
    return h5py.File(str(Path(h5_path).expanduser()), "r")


def read_response_data(
    h5_path: str | Path,
    epoch_uuid: str,
    device_name: str,
    *,
    h5path_hint: Optional[str] = None,
) -> np.ndarray:
    """Read a response sample array.

    If ``h5path_hint`` is provided (the ``Response.h5path`` column), it
    is used directly. Otherwise the file is searched for the matching
    ``epoch-{uuid}/responses/{device_name}/data`` dataset.
    """
    h5py = _import_h5py()
    with h5py.File(str(Path(h5_path).expanduser()), "r") as f:
        if h5path_hint:
            ds = f[h5path_hint]
        else:
            ds = _find_dataset(
                f, epoch_uuid=epoch_uuid, device=device_name, kind="responses"
            )
        data = ds[...]
    return _measurement_to_array(data)


def read_stimulus_data(
    h5_path: str | Path,
    epoch_uuid: str,
    device_name: str,
    *,
    h5path_hint: Optional[str] = None,
) -> np.ndarray:
    h5py = _import_h5py()
    with h5py.File(str(Path(h5_path).expanduser()), "r") as f:
        if h5path_hint:
            ds = f[h5path_hint]
        else:
            ds = _find_dataset(
                f, epoch_uuid=epoch_uuid, device=device_name, kind="stimuli"
            )
        data = ds[...]
    return _measurement_to_array(data)


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _measurement_to_array(data) -> np.ndarray:
    """Symphony stores response samples as a compound dtype
    ``{'quantity': float64, 'units': S10}``. Strip the units."""
    if data.dtype.names and "quantity" in data.dtype.names:
        return np.asarray(data["quantity"], dtype=np.float64)
    return np.asarray(data)


def _find_dataset(file, *, epoch_uuid: str, device: str, kind: str):
    """Walk the file looking for ``epoch-{epoch_uuid}/<kind>/<device>/data``.

    Returns the first match. Raises ``KeyError`` if not found.
    """
    target_group = f"epoch-{epoch_uuid}"
    found = []

    def visit(name, obj):
        if target_group in name and name.endswith(f"{kind}/{device}/data"):
            found.append(obj)

    file.visititems(visit)
    if not found:
        raise KeyError(
            f"No {kind} dataset for epoch {epoch_uuid}, device {device!r} in {file.filename}"
        )
    return found[0]
