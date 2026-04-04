#!/bin/sh
set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

check_writable() {
    _dir="$1"
    _identity="$2"
    _probe="$_dir/.musicseerr_write_test_$$"
    if [ -n "$_identity" ]; then
        gosu "$_identity" touch "$_probe" 2>/dev/null && gosu "$_identity" rm -f "$_probe" 2>/dev/null
    else
        touch "$_probe" 2>/dev/null && rm -f "$_probe" 2>/dev/null
    fi
}

if [ "$(id -u)" -ne 0 ]; then
    echo "[init] Running as uid=$(id -u) gid=$(id -g) (non-root); skipping user/group setup."
    for dir in /app/cache /app/config; do
        mkdir -p "$dir" 2>/dev/null || true
        if ! check_writable "$dir"; then
            echo "[init] FATAL: $dir is not writable by uid=$(id -u)."
            echo "[init]   Ensure the host directory is owned by this UID/GID."
            echo "[init]   Run: chown $(id -u):$(id -g) <host-path>"
            exit 1
        fi
    done
    exec "$@"
fi

if ! groupmod -o -g "$PGID" musicseerr 2>/dev/null; then
    echo "[init] WARNING: Could not set musicseerr group to GID=$PGID."
fi
if ! usermod -o -u "$PUID" musicseerr 2>/dev/null; then
    echo "[init] WARNING: Could not set musicseerr user to UID=$PUID."
fi

TARGET_UID=$(id -u musicseerr)
TARGET_GID=$(id -g musicseerr)
echo "[init] Runtime user: musicseerr (uid=$TARGET_UID gid=$TARGET_GID)"

for dir in /app/cache /app/config; do
    mkdir -p "$dir" 2>/dev/null || true

    if check_writable "$dir" "$TARGET_UID:$TARGET_GID"; then
        continue
    fi

    if chown -R musicseerr:musicseerr "$dir" 2>/dev/null; then
        echo "[init] Fixed ownership of $dir"
    else
        echo "[init] WARNING: Could not chown $dir (mount may not support ownership changes)."
    fi

    if ! check_writable "$dir" "$TARGET_UID:$TARGET_GID"; then
        echo "[init] FATAL: $dir is not writable by uid=$TARGET_UID gid=$TARGET_GID."
        echo "[init]   Common causes: FUSE/shfs (Unraid), NFS root_squash, CIFS/SMB, dropped CAP_CHOWN."
        echo "[init]   Fix: ensure the host directory is writable by uid=$TARGET_UID gid=$TARGET_GID."
        exit 1
    fi
done

exec gosu musicseerr:musicseerr "$@"
