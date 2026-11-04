#!/bin/bash
set -eu

# Wings supplies STARTUP and mounts a volume already owned by its runtime user.
if [[ "${STARTUP:-}" == "bash /opt/cs2-mods/start-pterodactyl.sh" ]]; then
    exec bash /opt/cs2-mods/start-pterodactyl.sh
fi

: "${STEAMAPPDIR:=/home/steam/cs2-dedicated}"
export STEAMAPPDIR
# setpriv changes credentials but does not reset root's inherited environment.
# SteamCMD needs a writable home, including Steam logs and cached client state.
export HOME=/home/steam USER=steam LOGNAME=steam

if [ "$(id -u)" -eq 0 ]; then
    # A newly created bind mount, or files from an older container, may belong
    # to root. Refuse critical system directories before changing ownership.
    data_dir="$(realpath -m -- "$STEAMAPPDIR")"
    case "$data_dir" in
        /|/home|/home/steam|/etc|/usr|/var|/opt|/tmp)
            echo "Refusing to use a system directory as STEAMAPPDIR: $data_dir" >&2
            exit 1
            ;;
    esac
    export STEAMAPPDIR="$data_dir"
    mkdir -p "$STEAMAPPDIR"
    echo "[entrypoint] Preparing data volume permissions for steam (1000:1000)"
    # Stay on the data filesystem and do not follow symlinks. Only chown entries
    # whose ownership differs, avoiding unnecessary metadata writes.
    find "$STEAMAPPDIR" -xdev \( ! -uid 1000 -o ! -gid 1000 \) \
        -exec chown -h 1000:1000 -- {} +
    exec setpriv --reuid=1000 --regid=1000 --init-groups "$0" "$@"
fi

mkdir -p "$STEAMAPPDIR"
# Refresh even when the data volume already contains an older hook.
# Replace a read-only old hook rather than opening it for writing.
cp --remove-destination /opt/cs2-mods/pre.sh "$STEAMAPPDIR/pre.sh"
exec "$@"
