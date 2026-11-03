#!/usr/bin/env python3
"""Install upstream CS2 releases before startup; keep state in the game volume."""

import os
from pathlib import Path

from mod_updater import log
from mod_updater.filesystem import volume_lock
from mod_updater.updater import Updater


def main() -> int:
    updater = Updater(Path(os.environ.get("STEAMAPPDIR", "/home/steam/cs2-dedicated")))
    try:
        with volume_lock(updater.state):
            updater.run()
    except Exception as error:  # noqa: BLE001 - Any startup error must stop CS2.
        log(f"FATAL: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
