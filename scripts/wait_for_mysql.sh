#!/usr/bin/env bash
# wait_for_mysql.sh — block until the Docker MySQL fixture is ready.
#
# Usage:
#   ./scripts/wait_for_mysql.sh             # wait up to 60s
#   ./scripts/wait_for_mysql.sh 30          # wait up to 30s

set -euo pipefail

HOST="${DJ_HOST:-127.0.0.1}"
PORT="${DJ_PORT:-3306}"
USER="${DJ_USER:-root}"
PASS="${DJ_PASSWORD:-simple}"
TIMEOUT="${1:-60}"

echo "Waiting up to ${TIMEOUT}s for MySQL at ${HOST}:${PORT}..."
for ((i = 0; i < TIMEOUT; i++)); do
    if mysqladmin --host="$HOST" --port="$PORT" --user="$USER" \
        --password="$PASS" ping >/dev/null 2>&1; then
        echo "MySQL is up."
        exit 0
    fi
    sleep 1
done

echo "Timed out waiting for MySQL." >&2
exit 1
