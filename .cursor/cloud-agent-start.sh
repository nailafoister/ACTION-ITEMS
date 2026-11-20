#!/usr/bin/env bash
set -euo pipefail
[ ! -d '/agent/repos/action-items' ] || cd '/agent/repos/action-items' || exit $?
PORT="${DASHBOARD_PORT:-8080}"
exec python3 -m http.server "$PORT" --bind 0.0.0.0 --directory docs