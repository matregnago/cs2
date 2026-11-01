#!/usr/bin/env python3
"""Install upstream CS2 releases before startup; keep state in the game volume."""

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile


MODS = {
    "metamod": ("alliedmodders/metamod-source", r"mmsource-2\..*-linux\.tar\.gz",
                ["addons/metamod.vdf", "addons/metamod/bin/linuxsteamrt64/metamod.2.cs2.so",
                 "addons/metamod/bin/linuxsteamrt64/libserver.so"]),
    "counterstrikesharp": ("roflmuffin/CounterStrikeSharp",
                          r"counterstrikesharp-with-runtime-linux-.*\.zip",
                          ["addons/counterstrikesharp/bin/linuxsteamrt64/counterstrikesharp.so",
                           "addons/counterstrikesharp/api/CounterStrikeSharp.API.dll",
                           "addons/counterstrikesharp/dotnet/shared/Microsoft.NETCore.App/*/libcoreclr.so"]),
    "matchzy": ("shobhit-pathak/MatchZy", r"MatchZy-(?!.*with-cssharp).*\.zip",
                ["addons/counterstrikesharp/plugins/MatchZy/MatchZy.dll"]),
    "inventory": ("ianlucas/cs2-css-inventory-simulator", r"InventorySimulator-.*\.zip",
                  ["addons/counterstrikesharp/plugins/InventorySimulator/InventorySimulator.dll"]),
}


def log(message):
    print(f"[mod-updater] {message}", flush=True)


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".mod-updater-tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def parse_admin_ids(value):
    if value is None or not value.strip():
        return None  # Preserve manually configured admins when not managed via env.
    if value.strip() == "[]":
        return []
    identifiers = list(dict.fromkeys(re.split(r"[,\s]+", value.strip())))
    if not all(re.fullmatch(r"[0-9]{17}", identifier) for identifier in identifiers):
        raise ValueError("CS2_ADMIN_STEAMIDS must contain comma/space-separated 17-digit SteamID64 values, or []")
    return identifiers


def patch_gameinfo(contents):
    if re.search(r"^[ \t]*Game[ \t]+csgo/addons/metamod[ \t]*(?://[^\n]*)?$", contents, re.MULTILINE):
        return contents
    # Prefer the low-violence search path without depending on the precise
    # wording of Valve's comment. Fall back to the standard path.
    anchor = re.search(r"^([ \t]*)Game_LowViolence[ \t]+csgo_lv[^\n]*$", contents, re.MULTILINE)
    if anchor:
        return (contents[:anchor.end()] + "\n" + anchor.group(1)
                + "Game\tcsgo/addons/metamod" + contents[anchor.end():])
    anchor = re.search(r"^([ \t]*)Game[ \t]+csgo[ \t]*(?://[^\n]*)?$", contents, re.MULTILINE)
    if not anchor:
        raise ValueError("could not locate CS2 Game search path in gameinfo.gi")
    return (contents[:anchor.start()] + anchor.group(1) + "Game\tcsgo/addons/metamod\n"
            + contents[anchor.start():])


class GitHub:
    def __init__(self, token=""):
        self.token = token

    def fetch(self, url, destination=None, api=False):
        headers = {"User-Agent": "cs2-mod-updater", "Accept": "application/vnd.github+json"}
        # Never forward the API token to asset/CDN URLs.
        if api and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        for attempt in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
                    if destination is None:
                        return json.load(response)
                    with destination.open("wb") as output:
                        shutil.copyfileobj(response, output)
                    return
            except (OSError, ValueError) as error:
                if attempt == 2:
                    # Avoid logging headers, tokens, or potentially sensitive response bodies.
                    raise RuntimeError(f"request failed ({type(error).__name__})") from None
                time.sleep(attempt + 1)

    def latest(self, repository):
        releases = []
        page = 1
        while True:
            batch = self.fetch(
                f"https://api.github.com/repos/{repository}/releases?per_page=100&page={page}", api=True)
            if not isinstance(batch, list):
                raise ValueError("invalid releases response")
            releases.extend(r for r in batch if not r.get("draft") and r.get("published_at"))
            if len(batch) < 100:
                break
            page += 1
        # Metamod also publishes Source 1 releases (1.x), which cannot load CS2.
        if repository == MODS["metamod"][0]:
            releases = [r for r in releases if r["tag_name"].startswith("2.")]
        if not releases:
            raise ValueError("no published releases")
        return max(releases, key=lambda r: (r["published_at"], r["id"]))


def essential_files(root, mod):
    return all(any(p.is_file() and p.stat().st_size > 0 for p in root.glob(pattern))
               for pattern in MODS[mod][2])


def archive_path(name):
    path = PurePosixPath(name)
    if "\\" in name or path.is_absolute() or ".." in path.parts or ":" in name:
        raise ValueError("unsafe archive path")
    # Packages must have the layout expected by CS2, not an arbitrary outer directory.
    if not path.parts or path.parts[0] not in ("addons", "cfg"):
        return None
    return Path(*path.parts)


def extract(archive, destination):
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                path = archive_path(member.filename)
                if stat.S_ISLNK(member.external_attr >> 16):
                    raise ValueError("archive symlinks are not supported")
                if path is None or member.is_dir():
                    continue
                target = destination / path
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod(0o755 if member.external_attr >> 16 & 0o111 else 0o644)
    else:
        with tarfile.open(archive, "r:gz") as bundle:
            for member in bundle:
                path = archive_path(member.name)
                if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                    raise ValueError("unsupported tar member")
                if path is None or member.isdir():
                    continue
                target = destination / path
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod(member.mode & 0o777)


def preserve_existing(path):
    name = path.as_posix()
    return (name.startswith(("cfg/", "addons/counterstrikesharp/configs/"))
            or "/spawns/" in name
            or path.suffix.lower() in (".cfg", ".ini", ".db", ".sqlite", ".sqlite3")
            or path.name.lower() == "admins.json")


def safe_target(root, relative):
    target = root / relative
    if not target.is_relative_to(root) or ".." in relative.parts:
        raise ValueError("target escapes game volume")
    for item in [target, *target.parents]:
        if item == root:
            break
        if item.is_symlink():
            raise ValueError("refusing to modify a symlink")
    if target.exists() and not target.is_file():
        raise ValueError("target is not a regular file")
    return target


class Transaction:
    """Back up every touched file before writing; recover interrupted writes next boot."""

    def __init__(self, root, state):
        self.root = root
        self.directory = state / "transaction"
        self.journal = self.directory / "journal.json"

    def recover(self):
        if self.journal.exists():
            log("Restoring previous installation from unfinished transaction")
            entries = json.loads(self.journal.read_text())
            for index, entry in reversed(list(enumerate(entries))):
                target = safe_target(self.root, Path(entry["path"]))
                target.with_name(target.name + ".mod-updater-tmp").unlink(missing_ok=True)
                if entry["existed"]:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(self.directory / str(index), target)
                else:
                    target.unlink(missing_ok=True)
            self.journal.unlink()
        if self.directory.exists():
            shutil.rmtree(self.directory)

    def apply(self, changes):
        self.directory.mkdir()
        entries = []
        for index, (relative, source) in enumerate(changes.items()):
            target = safe_target(self.root, relative)
            existed = target.exists()
            if existed:
                shutil.copy2(target, self.directory / str(index))
            entries.append({"path": relative.as_posix(), "existed": existed})
        atomic_write(self.journal, json_bytes(entries))
        try:
            for relative, source in changes.items():
                target = safe_target(self.root, relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(target.name + ".mod-updater-tmp")
                shutil.copy2(source, temporary)
                temporary.replace(target)
        except Exception:
            self.recover()  # Any recovery error is fatal, never eligible for fallback.
            raise
        self.journal.unlink()  # Commit point: all payloads and manifests are in place.
        shutil.rmtree(self.directory)


class Updater:
    def __init__(self, root, defaults=None, github=None):
        self.root = Path(root).absolute()
        self.game = self.root / "game/csgo"
        self.state = self.root / ".mod-updater"
        self.defaults = defaults or Path(__file__).parent / "cfg"
        self.github = github or GitHub(os.environ.get("GITHUB_TOKEN", ""))
        self.transaction = Transaction(self.root, self.state)
        self.admin_ids = None

    def complete(self):
        return all(essential_files(self.game, mod) for mod in MODS)

    def stage_updates(self, work):
        changes = {}
        updated = []
        for mod, (repository, pattern, _) in MODS.items():
            manifest_path = self.state / f"{mod}.json"
            try:
                installed = json.loads(manifest_path.read_text())
            except (OSError, ValueError):
                installed = {}
            if not isinstance(installed, dict):
                installed = {}
            release = self.github.latest(repository)
            assets = [a for a in release["assets"] if re.fullmatch(pattern, a["name"])]
            if len(assets) != 1:
                raise ValueError(f"{mod}: expected exactly one compatible asset, found {len(assets)}")
            asset = assets[0]
            manifest = {"repository": repository, "tag": release["tag_name"],
                        "release_id": release["id"], "asset_id": asset["id"]}
            log(f"{mod}: installed={installed.get('tag', 'unknown')}, upstream={manifest['tag']}")
            if manifest == installed and essential_files(self.game, mod):
                log(f"{mod}: unchanged; skipping download")
                continue
            archive = work / asset["name"]
            self.github.fetch(asset["browser_download_url"], archive)
            if archive.stat().st_size != asset["size"]:
                raise ValueError(f"{mod}: asset size mismatch")
            digest = asset.get("digest")
            if digest:
                if not digest.startswith("sha256:"):
                    raise ValueError(f"{mod}: unsupported asset digest")
                hasher = hashlib.sha256()
                with archive.open("rb") as data:
                    for chunk in iter(lambda: data.read(1024 * 1024), b""):
                        hasher.update(chunk)
                actual = hasher.hexdigest()
                if digest != f"sha256:{actual}":
                    raise ValueError(f"{mod}: asset checksum mismatch")
            staged = work / mod
            staged.mkdir()
            extract(archive, staged)
            if not essential_files(staged, mod):
                raise ValueError(f"{mod}: package is missing essential files")
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
            prepared_manifest = work / f"{mod}.json"
            prepared_manifest.write_bytes(json_bytes(manifest))
            changes[manifest_path.relative_to(self.root)] = prepared_manifest
            updated.append(mod)
        return changes, updated

    def configure_admins(self, work, changes):
        if self.admin_ids is None:
            return
        matchzy = {identifier: "" for identifier in self.admin_ids}
        relative = Path("game/csgo/cfg/MatchZy/admins.json")
        prepared = work / "matchzy-admins.json"
        prepared.write_bytes(json_bytes(matchzy))
        changes[relative] = prepared

        relative = Path("game/csgo/addons/counterstrikesharp/configs/admins.json")
        existing = safe_target(self.root, relative)
        source = existing if existing.exists() else changes.get(relative)
        admins = json.loads(source.read_text(encoding="utf-8-sig")) if source else {}
        if not isinstance(admins, dict):
            raise ValueError("CounterStrikeSharp admins.json must be a JSON object")
        # Reserve this prefix for env-managed accounts; retain all manual entries.
        admins = {key: value for key, value in admins.items() if not key.startswith("cs2-docker-")}
        for identifier in self.admin_ids:
            admins[f"cs2-docker-{identifier}"] = {"identity": identifier, "flags": ["@css/root"]}
        prepared = work / "css-admins.json"
        prepared.write_bytes(json_bytes(admins))
        changes[relative] = prepared

    def configure(self, work, changes):
        for source in self.defaults.rglob("*"):
            if source.is_file():
                relative = Path("game/csgo/cfg") / source.relative_to(self.defaults)
                if not safe_target(self.root, relative).exists():
                    changes[relative] = source

        self.configure_admins(work, changes)

        relative = Path("game/csgo/addons/counterstrikesharp/configs/core.json")
        existing = safe_target(self.root, relative)
        example = relative.with_name("core.example.json")
        source = existing if existing.exists() else changes.get(relative, changes.get(example, self.root / example))
        config = json.loads(source.read_text(encoding="utf-8-sig"))
        config["FollowCS2ServerGuidelines"] = False
        core = work / "core.json"
        core.write_bytes(json_bytes(config))
        if not existing.exists() or json.loads(existing.read_text(encoding="utf-8-sig")) != config:
            changes[relative] = core

        relative = Path("game/csgo/gameinfo.gi")
        gameinfo = safe_target(self.root, relative).read_text()
        patched = patch_gameinfo(gameinfo)
        if patched != gameinfo:
            prepared = work / "gameinfo.gi"
            prepared.write_text(patched)
            changes[relative] = prepared

    def run(self):
        # Invalid admin settings must stop startup before downloads or fallback.
        self.admin_ids = parse_admin_ids(os.environ.get("CS2_ADMIN_STEAMIDS"))
        self.state.mkdir(parents=True, exist_ok=True)
        # Recovery failures must stop startup, even if essential binaries still exist.
        self.transaction.recover()
        with tempfile.TemporaryDirectory(prefix="staging-", dir=self.state) as directory:
            work = Path(directory)
            try:
                changes, updated = self.stage_updates(work)
                self.configure(work, changes)
                self.transaction.apply(changes)
            except Exception as error:
                if self.transaction.journal.exists() or not self.complete():
                    raise RuntimeError(f"update failed; no complete safe installation ({error})") from error
                self.transaction.recover()
                log(f"Update failed: {error}; using previous installation")
                # SteamCMD may have overwritten gameinfo.gi even when GitHub is offline.
                changes = {}
                self.configure(work, changes)
                self.transaction.apply(changes)
                for mod in MODS:
                    try:
                        tag = json.loads((self.state / f"{mod}.json").read_text())["tag"]
                    except (OSError, ValueError, KeyError, TypeError):
                        tag = "unknown (unmanaged installation)"
                    log(f"{mod}: keeping installed version {tag}")
                return
            for mod in updated:
                log(f"{mod}: update applied")


@contextlib.contextmanager
def volume_lock(state):
    state.mkdir(parents=True, exist_ok=True)
    with (state / "updater.lock").open("a+b") as lock:
        if os.name == "nt":
            import msvcrt
            if lock.tell() == 0:
                lock.write(b"\0")
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patch-gameinfo", type=Path, metavar="FILE",
                        help="only patch the specified gameinfo.gi; do not query upstream")
    arguments = parser.parse_args()
    if arguments.patch_gameinfo is not None:
        try:
            path = arguments.patch_gameinfo
            if path.is_symlink():
                raise ValueError("refusing to modify a symlink")
            original = path.read_text()
            patched = patch_gameinfo(original)
            if patched != original:
                atomic_write(path, patched.encode())
                log("Metamod search path added to gameinfo.gi")
            else:
                log("Metamod search path already present in gameinfo.gi")
            return 0
        except Exception as error:
            log(f"FATAL: {error}")
            return 1
    updater = Updater(os.environ.get("STEAMAPPDIR", "/home/steam/cs2-dedicated"))
    try:
        with volume_lock(updater.state):
            updater.run()
    except Exception as error:
        log(f"FATAL: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
