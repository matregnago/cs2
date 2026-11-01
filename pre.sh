#!/bin/bash
# The upstream entry script sources this hook after SteamCMD has updated CS2.
# Explicit exit is required: upstream does not check the hook's return code.
python3 /opt/cs2-mods/update_mods.py || exit 1
