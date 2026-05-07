#!/usr/bin/env bash
# wait_for_mysql.sh — block until the Docker MySQL fixture is ready.
#
# Strategy (no host-side mysqladmin required):
#   1. If the docker-compose service is up, poll its container health
#      status (set by the healthcheck in config/docker-compose.yaml).
#   2. Fall back to a TCP probe on 127.0.0.1:3306 via /dev/tcp.
#
# Usage:
#   ./scripts/wait_for_mysql.sh             # default 180s timeout
#   ./scripts/wait_for_mysql.sh 60          # custom timeout in seconds

set -eu

CONTAINER="${MYSQL_CONTAINER:-datajoint_symphony_mysql}"
HOST="${DJ_HOST:-127.0.0.1}"
PORT="${DJ_PORT:-3306}"
TIMEOUT="${1:-180}"

echo "Waiting up to ${TIMEOUT}s for MySQL (container=${CONTAINER}, ${HOST}:${PORT})..."

for ((i = 0; i < TIMEOUT; i++)); do
    # Preferred path: Docker healthcheck status.
    if docker inspect "$CONTAINER" >/dev/null 2>&1; then
        status=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$CONTAINER" 2>/dev/null || echo "unknown")
        case "$status" in
            healthy)
                echo "MySQL is healthy."
                exit 0
                ;;
            unhealthy)
                echo "Container reports unhealthy. Recent logs:" >&2
                docker logs --tail 30 "$CONTAINER" >&2 || true
                exit 1
                ;;
            none|unknown|starting|"")
                : # keep waiting
                ;;
        esac
    fi

    # Fallback: bash /dev/tcp probe (no nc/mysqladmin dependency).
    if (echo > /dev/tcp/"$HOST"/"$PORT") >/dev/null 2>&1; then
        # TCP open — but MySQL's auth handshake takes a moment after the port
        # binds. Wait one more second so the next caller's connect() succeeds.
        sleep 1
        echo "MySQL TCP port is open."
        exit 0
    fi

    sleep 1
    if (( i % 10 == 0 && i > 0 )); then
        printf "  ...still waiting (%ds)\n" "$i"
    fi
done

echo "Timed out after ${TIMEOUT}s." >&2
if docker inspect "$CONTAINER" >/dev/null 2>&1; then
    echo "Last 50 lines of container log:" >&2
    docker logs --tail 50 "$CONTAINER" >&2 || true
fi
exit 1
