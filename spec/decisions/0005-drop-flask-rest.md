# ADR 0005 — Drop the Flask REST surface; library + CLI only

**Status:** Accepted
**Date:** 2026-05-06

## Context

The legacy `app.py` was a Flask app that wrapped `helpers/init.py`,
`helpers/pop.py`, and `helpers/query.py` as HTTP endpoints, intended to
back an Electron front-end. The team has settled on driving the
DataJoint pipeline directly from Python and Jupyter; nobody is actively
using the Electron UI, and the Flask layer adds:

- A second authentication / CORS surface.
- A second config surface (which port, which host).
- A second testing surface (HTTP fixtures, request mocking).
- Background-thread bookkeeping (`add_data_started`,
  `_add_data_thread`) that didn't survive process restarts and was a
  source of "stuck" states.

## Decision

`symphony_dj` ships as a **Python library** with a small **CLI**:

```
python -m symphony_dj init                  # create schema
python -m symphony_dj ingest <path>         # ingest a JSON or directory
python -m symphony_dj query --protocol ...  # run a query, print to stdout
```

No HTTP server, no CORS, no threads, no Flask. The legacy `app.py`
stays under `old/` for reference.

## Consequences

**Good**

- Smaller surface to test, document, and maintain.
- Clearer error semantics — exceptions bubble up where the user can see
  them, instead of being swallowed by a Flask handler and converted to
  a 400.
- Compatible with notebook-driven science. `from symphony_dj import
  connect; db = connect(); ...` is the day-to-day pattern.

**Cost**

- The Electron UI, if anyone resurrects it, would need to wrap the
  library itself. We accept this. A future ADR can add a thin REST
  wrapper *if* there's actual demand; the library is structured to make
  that wrapper a 200-line file.

## Alternatives considered

- **Keep Flask, fix v2.0 issues.** Considered; rejected because it
  would lock in two-track maintenance for a UI nobody is currently
  using. The cost of resurrecting it later is small (the library has
  the same surface area Flask was wrapping).
- **FastAPI rewrite.** Modern Flask alternative. Rejected for the same
  reason — no consumer at the moment.
