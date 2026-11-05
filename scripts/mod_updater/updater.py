"""Stage and validate a full update before committing it to the game volume."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from . import log
from .archives import extract
from .catalog import MODS
from .configuration import configure, parse_admin_ids, preserve_existing
from .filesystem import Changes, Transaction, json_bytes, safe_target
from .github import GitHub


def read_manifest(path: Path) -> dict:
    """Treat missing or invalid state as an unmanaged installation."""
    try:
        manifest = json.loads(path.read_text())
        return manifest if isinstance(manifest, dict) else {}
    except (OSError, ValueError):
        return {}


class Updater:
    def __init__(
        self, root: Path, defaults: Path | None = None, github: GitHub | None = None
    ):
        self.root = Path(root).absolute()
        self.game = self.root / "game/csgo"
        self.state = self.root / ".mod-updater"
        self.defaults = defaults or Path(__file__).parent.parent / "cfg"
        self.github = github or GitHub()
        self.transaction = Transaction(self.root, self.state)

    def complete(self) -> bool:
        return all(mod.is_installed(self.game) for mod in MODS)

    def stage_updates(self, work: Path) -> tuple[Changes, list[str]]:
        changes: Changes = {}
        updated = []
        for mod in MODS:
            manifest_path = self.state / f"{mod.name}.json"
            installed = read_manifest(manifest_path)
            release = self.github.latest(
                mod.repository, tag_prefix=mod.release_tag_prefix
            )
            assets = [
                asset
                for asset in release["assets"]
                if re.fullmatch(mod.asset_pattern, asset["name"])
            ]
            if len(assets) != 1:
                raise ValueError(
                    f"{mod.name}: expected exactly one compatible asset, found {len(assets)}"
                )
            asset = assets[0]
            manifest = {
                "repository": mod.repository,
                "tag": release["tag_name"],
                "release_id": release["id"],
                "asset_id": asset["id"],
            }
            log(
                f"{mod.name}: installed={installed.get('tag', 'unknown')}, "
                f"upstream={manifest['tag']}"
            )
            if manifest == installed and mod.is_installed(self.game):
                log(f"{mod.name}: unchanged; skipping download")
                continue
            archive = work / asset["name"]
            self.github.download(asset, archive)
            staged = work / mod.name
            staged.mkdir()
            extract(archive, staged, mod.archive_prefix, mod.windows_archive_paths)
            if mod.plugin_directory:
                plugins = staged / "addons/counterstrikesharp/plugins"
                disabled = plugins / "disabled"
                disabled.mkdir(exist_ok=True)
                (plugins / mod.plugin_directory).rename(disabled / mod.plugin_directory)
            if mod.name in ("instadefuse", "retakes-allocator"):
                old_plugin = Path(
                    "game/csgo/addons/counterstrikesharp/plugins"
                ) / mod.plugin_directory / f"{mod.plugin_directory}.dll"
                if safe_target(self.root, old_plugin).exists():
                    changes[old_plugin] = None
            if not mod.is_installed(staged):
                raise ValueError(f"{mod.name}: package is missing essential files")
            for source in staged.rglob("*"):
                if not source.is_file():
                    continue
                relative = source.relative_to(staged)
                target = safe_target(self.game, relative)
                if preserve_existing(relative) and target.exists():
                    continue
                destination = Path("game/csgo") / relative
                if destination in changes:
                    raise ValueError(f"overlapping package files: {relative}")
                changes[destination] = source
            prepared_manifest = work / f"{mod.name}.json"
            prepared_manifest.write_bytes(json_bytes(manifest))
            changes[manifest_path.relative_to(self.root)] = prepared_manifest
            updated.append(mod.name)
        return changes, updated

    def run(self) -> None:
        # Invalid admin settings must stop startup before downloads or fallback.
        admin_ids = parse_admin_ids(os.environ.get("CS2_ADMIN_STEAMIDS"))
        self.state.mkdir(parents=True, exist_ok=True)
        # Recovery failures must stop startup, even if essential binaries still exist.
        self.transaction.recover()
        with tempfile.TemporaryDirectory(
            prefix="staging-", dir=self.state
        ) as directory:
            work = Path(directory)
            try:
                changes, updated = self.stage_updates(work)
                configure(self.root, self.defaults, admin_ids, work, changes)
                self.transaction.apply(changes)
            except Exception as error:
                if self.transaction.journal.exists() or not self.complete():
                    raise RuntimeError(
                        f"update failed; no complete safe installation ({error})"
                    ) from error
                self.transaction.recover()
                log(f"Update failed: {error}; using previous installation")
                # SteamCMD may have overwritten gameinfo.gi even when GitHub is offline.
                changes = {}
                configure(self.root, self.defaults, admin_ids, work, changes)
                self.transaction.apply(changes)
                for mod in MODS:
                    installed = read_manifest(self.state / f"{mod.name}.json")
                    tag = installed.get("tag", "unknown (unmanaged installation)")
                    log(f"{mod.name}: keeping installed version {tag}")
                return
            for name in updated:
                log(f"{name}: update applied")
