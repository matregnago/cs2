#!/bin/bash
# The upstream entry script sources this hook after SteamCMD has updated CS2.
# Explicit exit is required: upstream does not check the hook's return code.
python3 /opt/cs2-mods/update_mods.py || exit 1

# The upstream launcher reads these arguments after sourcing this hook.
CS2_ADDITIONAL_ARGS="${CS2_ADDITIONAL_ARGS:-}"
if [[ -n "${CS2_AUTHKEY:-}" ]]; then
    # Upstream uses eval, so escape the key as one shell argument.
    printf -v cs2_authkey_arg '%q' "$CS2_AUTHKEY"
    CS2_ADDITIONAL_ARGS+=" -authkey ${cs2_authkey_arg}"
fi
CS2_ADDITIONAL_ARGS+=" +exec inventory_simulator.cfg"
