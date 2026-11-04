"""Prepare persistent defaults, managed admins, and loader configuration."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .filesystem import Changes, json_bytes, safe_target


def parse_admin_ids(value: str | None) -> list[str] | None:
    value = (value or "").strip()
    if not value:
        return None  # Preserve manually configured admins when not managed via env.
    if value == "[]":
        return []
    identifiers = list(dict.fromkeys(re.split(r"[,\s]+", value)))
    if not all(re.fullmatch(r"[0-9]{17}", identifier) for identifier in identifiers):
        raise ValueError(
            "CS2_ADMIN_STEAMIDS must contain comma/space-separated "
            "17-digit SteamID64 values, or []"
        )
    return identifiers


def patch_gameinfo(contents: str) -> str:
    if re.search(
        r"^[ \t]*Game[ \t]+csgo/addons/metamod[ \t]*(?://[^\n]*)?$",
        contents,
        re.MULTILINE,
    ):
        return contents
    # Prefer the low-violence search path without depending on the precise
    # wording of Valve's comment. Fall back to the standard path.
    anchor = re.search(
        r"^([ \t]*)Game_LowViolence[ \t]+csgo_lv[^\n]*$", contents, re.MULTILINE
    )
    if anchor:
        return (
            contents[: anchor.end()]
            + "\n"
            + anchor.group(1)
            + "Game\tcsgo/addons/metamod"
            + contents[anchor.end() :]
        )
    anchor = re.search(
        r"^([ \t]*)Game[ \t]+csgo[ \t]*(?://[^\n]*)?$", contents, re.MULTILINE
    )
    if not anchor:
        raise ValueError("could not locate CS2 Game search path in gameinfo.gi")
    return (
        contents[: anchor.start()]
        + anchor.group(1)
        + "Game\tcsgo/addons/metamod\n"
        + contents[anchor.start() :]
    )


def preserve_existing(path: Path) -> bool:
    name = path.as_posix()
    return (
        name.startswith(("cfg/", "addons/counterstrikesharp/configs/"))
        or "/spawns/" in name
        or name.startswith(
            "addons/counterstrikesharp/plugins/disabled/RetakesPlugin/map_config/"
        )
        or path.suffix.lower() in (".cfg", ".ini", ".db", ".sqlite", ".sqlite3")
        or path.name.lower() == "admins.json"
    )


def configure_admins(
    root: Path, admin_ids: list[str] | None, work: Path, changes: Changes
) -> None:
    if admin_ids is None:
        return
    matchzy = {identifier: "" for identifier in admin_ids}
    relative = Path("game/csgo/cfg/MatchZy/admins.json")
    prepared = work / "matchzy-admins.json"
    prepared.write_bytes(json_bytes(matchzy))
    changes[relative] = prepared

    relative = Path("game/csgo/addons/counterstrikesharp/configs/admins.json")
    existing = safe_target(root, relative)
    source = existing if existing.exists() else changes.get(relative)
    admins = json.loads(source.read_text(encoding="utf-8-sig")) if source else {}
    if not isinstance(admins, dict):
        raise TypeError("CounterStrikeSharp admins.json must be a JSON object")
    # Reserve this prefix for env-managed accounts; retain all manual entries.
    admins = {
        key: value for key, value in admins.items() if not key.startswith("cs2-docker-")
    }
    for identifier in admin_ids:
        admins[f"cs2-docker-{identifier}"] = {
            "identity": identifier,
            "flags": ["@css/root"],
        }
    prepared = work / "css-admins.json"
    prepared.write_bytes(json_bytes(admins))
    changes[relative] = prepared


def configure(
    root: Path,
    defaults: Path,
    admin_ids: list[str] | None,
    work: Path,
    changes: Changes,
) -> None:
    """Add required configuration to the transaction without modifying live files."""
    for source in defaults.rglob("*"):
        if source.is_file():
            relative = Path("game/csgo/cfg") / source.relative_to(defaults)
            if not safe_target(root, relative).exists():
                changes[relative] = source

    configure_admins(root, admin_ids, work, changes)

    chat_control = Path(
        "game/csgo/addons/counterstrikesharp/configs/plugins/ChatControl/ChatControl.json"
    )
    if not safe_target(root, chat_control).exists():
        changes[chat_control] = Path(__file__).parent.parent / "ChatControl.json"

    relative = Path("game/csgo/addons/counterstrikesharp/configs/core.json")
    existing = safe_target(root, relative)
    example = relative.with_name("core.example.json")
    source = existing if existing.exists() else changes.get(relative)
    if source is None:
        source = changes.get(example, root / example)
    config = json.loads(source.read_text(encoding="utf-8-sig"))
    original = config.copy()
    config["FollowCS2ServerGuidelines"] = False
    if not existing.exists() or config != original:
        core = work / "core.json"
        core.write_bytes(json_bytes(config))
        changes[relative] = core

    relative = Path("game/csgo/gameinfo.gi")
    gameinfo = safe_target(root, relative).read_text()
    patched = patch_gameinfo(gameinfo)
    if patched != gameinfo:
        prepared = work / "gameinfo.gi"
        prepared.write_text(patched)
        changes[relative] = prepared
