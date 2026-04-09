#!/bin/sh
set -e

SQLITE_PATH="${SQLITE_PATH:-/app/data/db.sqlite3}"
SQLITE_DIR="$(dirname "$SQLITE_PATH")"

mkdir -p "$SQLITE_DIR"

if [ ! -f "$SQLITE_PATH" ] && [ -f /app/db.sqlite3 ]; then
  cp /app/db.sqlite3 "$SQLITE_PATH"
fi

python manage.py migrate --noinput

exec "$@"
