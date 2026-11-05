#!/bin/bash
set -euo pipefail

# Wings mounts the server volume at /home/container and selects the runtime UID.
if [[ "$(id -u)" == 0 ]]; then
    echo "Run this launcher as the Wings server user." >&2
    exit 1
fi
export HOME=/home/container USER=container LOGNAME=container
export STEAMAPPDIR="$HOME"
cd "$HOME"

if [[ "${CS2_AUTO_UPDATE:-1}" == 1 ]]; then
    (
        cd steamcmd
        ./steamcmd.sh +force_install_dir "$STEAMAPPDIR" +login anonymous +app_update 730 +quit
    )
    install -m 644 steamcmd/linux64/steamclient.so "$HOME/.steam/sdk64/steamclient.so"
fi

python3 /opt/cs2-mods/update_mods.py

args=(
    -dedicated -console -ip 0.0.0.0 -port "${SERVER_PORT:?Wings must supply SERVER_PORT}"
    -maxplayers "${CS2_MAXPLAYERS:-15}"
    +game_type 0 +game_mode 1 +mapgroup mg_active
    +hostname "${CS2_SERVERNAME:-CS2 Modded}" +sv_lan 0
)
if [[ -n "${CS2_PW:-}" ]]; then
    args+=(+sv_password "$CS2_PW")
fi
if [[ -n "${CS2_RCONPW:-}" ]]; then
    args+=(-usercon +rcon_password "$CS2_RCONPW")
fi
if [[ -n "${STEAM_GSLT:-}" ]]; then
    args+=(+sv_setsteamaccount "$STEAM_GSLT")
fi
if [[ -n "${CS2_AUTHKEY:-}" ]]; then
    args+=(-authkey "$CS2_AUTHKEY")
fi

cd "$HOME/game"

exec ./cs2.sh "${args[@]}" \
    +map "${CS2_STARTMAP:-de_mirage}" \
    +exec inventory_simulator.cfg
