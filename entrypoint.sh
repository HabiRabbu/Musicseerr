#!/bin/sh
set -e

PUID=${PUID:-911}
PGID=${PGID:-911}

groupmod -o -g "$PGID" musicseerr 2>/dev/null || true
usermod -o -u "$PUID" musicseerr 2>/dev/null || true

chown -R musicseerr:musicseerr /app/cache /app/config

exec gosu musicseerr:musicseerr "$@"
