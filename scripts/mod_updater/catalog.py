"""Supported mods, their release selection rules, and installation checks."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Mod:
    name: str
    repository: str
    asset_pattern: str
    required_files: tuple[str, ...]
    release_tag_prefix: str = ""
    plugin_directory: str = ""
    archive_prefix: str = ""

    def is_installed(self, root: Path) -> bool:
        """Each required glob must match at least one nonempty file."""
        return all(
            any(
                path.is_file() and path.stat().st_size > 0
                for path in root.glob(pattern)
            )
            for pattern in self.required_files
        )


# Order matters: install the loaders before their plugins.
MODS = (
    Mod(
        name="metamod",
        repository="alliedmodders/metamod-source",
        asset_pattern=r"mmsource-2\..*-linux\.tar\.gz",
        required_files=(
            "addons/metamod.vdf",
            "addons/metamod/bin/linuxsteamrt64/metamod.2.cs2.so",
            "addons/metamod/bin/linuxsteamrt64/libserver.so",
        ),
        # Metamod 1.x targets Source 1 and cannot load CS2.
        release_tag_prefix="2.",
    ),
    Mod(
        name="counterstrikesharp",
        repository="roflmuffin/CounterStrikeSharp",
        asset_pattern=r"counterstrikesharp-with-runtime-linux-.*\.zip",
        required_files=(
            "addons/counterstrikesharp/bin/linuxsteamrt64/counterstrikesharp.so",
            "addons/counterstrikesharp/api/CounterStrikeSharp.API.dll",
            "addons/counterstrikesharp/dotnet/shared/Microsoft.NETCore.App/*/libcoreclr.so",
        ),
    ),
    Mod(
        name="matchzy",
        repository="shobhit-pathak/MatchZy",
        asset_pattern=r"MatchZy-(?!.*with-cssharp).*\.zip",
        required_files=("addons/counterstrikesharp/plugins/MatchZy/MatchZy.dll",),
    ),
    Mod(
        name="retakes",
        repository="B3none/cs2-retakes",
        asset_pattern=r"RetakesPlugin-[0-9]+\.[0-9]+\.[0-9]+\.zip",
        required_files=(
            "addons/counterstrikesharp/plugins/disabled/RetakesPlugin/RetakesPlugin.dll",
            "addons/counterstrikesharp/plugins/disabled/RetakesPlugin/map_config/de_mirage.json",
            "addons/counterstrikesharp/shared/RetakesPluginShared/RetakesPluginShared.dll",
        ),
        plugin_directory="RetakesPlugin",
    ),
    Mod(
        name="chatcontrol",
        repository="timche/cs2-chat-control",
        asset_pattern=r"ChatControl-.*\.zip",
        required_files=(
            "addons/counterstrikesharp/plugins/ChatControl/ChatControl.dll",
        ),
        archive_prefix="addons/counterstrikesharp/plugins",
    ),
    Mod(
        name="inventory",
        repository="ianlucas/cs2-css-inventory-simulator",
        asset_pattern=r"InventorySimulator-.*\.zip",
        required_files=(
            "addons/counterstrikesharp/plugins/InventorySimulator/InventorySimulator.dll",
        ),
    ),
)
