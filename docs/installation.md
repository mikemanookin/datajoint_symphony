# Installation

## Prerequisites

- Python 3.10+ (the dataclasses with `kw_only` etc. used in the loader
  need this).
- Docker Desktop (for the local MySQL fixture). On Linux, plain Docker
  + Compose works.
- HDF5 system libraries — only required if you'll read raw samples
  (`pip install h5py` will install them on most platforms).

## 1. Clone and install

```bash
git clone https://github.com/Manookin-Lab/datajoint_symphony.git
cd datajoint_symphony

# Editable install (recommended during development):
pip install -e '.[dev]'

# Or production install:
pip install -e .
```

If your project doesn't yet ship a `pyproject.toml`, install the
runtime dependencies directly:

```bash
pip install datajoint pyyaml pymysql h5py numpy pandas tqdm
pip install pytest pytest-mock                  # tests
```

## 2. Start MySQL

The repo ships a Docker Compose file that brings up a MySQL 8 instance
matching the default `config/datajoint_config.yaml`:

```bash
cd config
docker compose up -d
./../scripts/wait_for_mysql.sh         # blocks until ready
cd ..
```

Stop with `docker compose down`. Add `-v` to wipe the data volume.

## 3. Connect

```bash
python -m symphony_dj init
```

Successful output looks like:

```
Connected: <symphony_dj.Database schema='symphony' host='127.0.0.1'>
Tables: 17
```

## 4. Configure (optional)

The default `config/datajoint_config.yaml` matches the Docker fixture.
For a non-Docker setup, copy it and edit:

```bash
cp config/datajoint_config.yaml ~/.datajoint_config.yaml
chmod 600 ~/.datajoint_config.yaml
$EDITOR ~/.datajoint_config.yaml
```

Or override individual fields with env vars (no file needed):

```bash
export DJ_HOST=mysql.lab.example.com
export DJ_USER=mike
export DJ_PASSWORD='see-1Password'
export DJ_SCHEMA=symphony_prod
python -m symphony_dj init
```

Full configuration reference: [`configuration.md`](configuration.md).

## 5. Ingest some data

```bash
python -m symphony_dj ingest /Volumes/data/data/json/20260410H_dj.json
```

See [`ingestion_guide.md`](ingestion_guide.md).

## Troubleshooting

- **`pymysql.err.OperationalError 2003`** — MySQL isn't reachable.
  Check `docker ps`; if the container is up, `docker compose logs mysql`.
- **`KeyError: 'database.host'`** — `dj.config` wasn't populated. You
  probably called a DataJoint API before `connect()`. Always go through
  `from symphony_dj import connect`.
- **Mac: ARM-only h5py wheel issues** — try
  `pip install --no-binary=h5py h5py` on Apple Silicon if the bundled
  HDF5 doesn't load.
