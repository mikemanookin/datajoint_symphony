"""Entry point so ``python src/python/app.py ...`` runs the CLI.

The package proper lives in :mod:`symphony_dj`. Day-to-day use is
``from symphony_dj import connect`` or ``python -m symphony_dj ...``;
this file exists only as a convenience launcher.
"""
from __future__ import annotations

import sys

from symphony_dj.cli import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
